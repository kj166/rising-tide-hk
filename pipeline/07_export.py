"""Step 7: Export site data (EPSG:4326) for the static website (decisions 2026-10-08).

Export contract (docs/internal/NOTES.md, Week 5): only derived results, banded or rounded, go to
site/public/data/. Allowed: asset no., name, district, point, footprint polygon (iB1000, attributed), tier
(absolute and relative), assets-to-watch flags, lowest flooding return period per scenario (with the
+/-0.15 m onset range), rain class and percentile band, landslide class, HLC points (attributes unaltered,
attributed), portfolio EAL ranges, adaptation break-even ranges, scorecard items and scores, a few cited
heat figures and the illustrative cooling what-if range, and the raise-the-sea extents (bathtub polygons on
the LandsD 5 m DTM per whole-metre still-water level, property pass_m only; design brief 2026-10-08), the terrain
tiles (terrain/{z}/{x}/{y}.png, terrarium-encoded LandsD 5 m DTM, attributed; decision 2026-10-08), and per asset and
scenario has_coastal_loss (boolean, no money; decision 2026-10-08), and margin facts for named assets (margins.json:
onset minus still-water level in whole cm, whether a rarer level reaches the site, and the asset's valuation rank; never
the mPD levels themselves; decision 2026-10-08).
Never: per-asset Link inputs (replacement cost, valuation, income, GFA / IFA, car spaces), the relative-lens
ratio, station-level or onset water levels, the continuous rain score, DSD points, AXA rows, transcribed
third-party tables (Arcadis, PWDM, HKO, Hazus, JRC). FORBIDDEN_KEYS is checked by tests/test_07_export.py.
Money: HK$ to 2 significant figures, as ranges (truncated-tail; BI 50%-maximum days); per-asset HK$ only
for the top coastal assets. Shares (%) also to 2 significant figures, never with decimals (e.g. 42-56%; decision
2026-10-08).

Inputs: data/interim/assets.geojson, asset_footprints.geojson, asset_values.csv (status only),
data/processed/exposure.parquet, impact.csv, impact_portfolio.csv, ranking.csv, hotspots.csv,
adaptation.csv, heat_whatif.csv, impact_observed_summary.csv, hazards/rain_assets.csv,
hazards/landslide_assets.csv, hazards/flood_extents.gpkg, data/raw/geo_landslide/HLC_1924-2019.gdb, data/manual/audit_scores.csv,
config (scenarios.yaml heat values via the config/local overlay).

Outputs: site/public/data/assets.geojson, footprints.geojson, hlc.geojson, flood_extents.geojson,
portfolio.json, adaptation.json, scorecard.json, heat.json, meta.json, terrain/ (PNG tiles; the only directory)
"""

import json
import math
import shutil
import sys
from pathlib import Path

import geopandas as gpd
from shapely.geometry import mapping
import numpy as np
import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.config import load_config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PROC, INTERIM, HAZ = ROOT / "data" / "processed", ROOT / "data" / "interim", ROOT / "data" / "processed" / "hazards"
OUT = ROOT / "site" / "public" / "data"
SCENARIOS = ["baseline", "ssp245_2050", "ssp585_2050", "ssp585_2100"]
SCENARIO_LABELS = {"baseline": "1995–2014 climate", "ssp245_2050": "SSP2-4.5 2050", "ssp585_2050": "SSP5-8.5 2050",
                   "ssp585_2100": "SSP5-8.5 2100 (sensitivity)"}
HEADLINE_SCENARIO = "ssp245_2050"

# keys that must never appear in site/public/data (checked by tests/test_07_export.py)
FORBIDDEN_KEYS = {
    "replacement_cost_hkd_low", "replacement_cost_hkd_mid", "replacement_cost_hkd_high", "value_hkd",
    "net_passing_income_hkd", "gfa_m2", "ifa_m2", "car_park_spaces", "coastal_eal_pct_income",
    "eal_pct_income", "level_mpd", "onset_level_mpd", "entry_level_mpd", "lowest_floor_mpd", "esl_mpd",
    "level_station_high_mpd", "rain_score_cont", "rain_index", "rain_index_cont", "dsd_nearest_m",
    "dsd_blockage_m", "pd_pct", "pd_hkd", "bi_days", "bi_hkd", "station", "income", "cap_rate", "initial_yield"}
FORBIDDEN_FILES = ("coastal_levels", "dsd", "axa", "station", "values", "claims")
# the only property allowed on flood_extents.geojson features (checked by tests/test_07_export.py)
EXTENT_KEYS = {"pass_m"}
# Level rule (decision 2026-10-12, rewording of 2026-10-08): absolute ground, entrance, floor or sill levels are never
# published as numbers. Results are published as return periods with their +/-0.15 m range, which bound those levels;
# this is accepted because the levels derive from open CEDD LiDAR and the published form carries its uncertainty.
# Relative margins in cm are published only for The Quayside (2050 margins) and Chai Wan Car Service Centre (Mangkhut
# replay offsets).
MARGIN_EXCEPTION = {"assets": {126}, "events": {129}}
MARGIN_KEYS = {"margins_cm", "margin_cm", "above_entry_cm", "below_floor_cm"}
LEVEL_KEY_ALLOW = {"observed_peak_mcd"}   # the cited HKO gauge reading (Quarry Bay), not a property level
TERRAIN_DIR = "terrain"   # the only directory in site/public/data (PNG tiles only)


def sig(x, n: int = 2):
    """Round to n significant figures; None for missing."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    x = float(x)
    if x == 0:
        return 0.0
    return round(x, -int(math.floor(math.log10(abs(x)))) + n - 1)


def money_range(lo, hi) -> list:
    """[low, high] in HK$, 2 significant figures, ordered."""
    a, b = sig(lo), sig(hi)
    return sorted([a, b]) if a is not None and b is not None else [a, b]


def top_share(loss: pd.Series, n: int = 3, other: pd.Series | None = None) -> tuple[list[int], float | None, float | None]:
    """The n largest positive entries of `loss` (index = valuation no.) and their share of the total; with `other`
    (a second loss basis on the same index), also the same assets' share of that total. Shares in %."""
    pos = loss[loss > 0].sort_values(ascending=False, kind="stable")
    if pos.empty:
        return [], None, None
    top = pos.index[:n].tolist()
    share = 100 * pos.loc[top].sum() / pos.sum()
    share_other = 100 * other.loc[top].sum() / other.sum() if other is not None and other.sum() > 0 else None
    return [int(x) for x in top], float(share), (None if share_other is None else float(share_other))


def margin_facts(onset_mpd: float, levels: pd.Series, flooded: pd.Series, cases: list[dict], reach_cases: list[dict]) -> dict:
    """Margins (whole cm, onset minus still-water level; negative = exceeded) for `cases`, and whether the asset is
    flooded for `reach_cases`. levels / flooded are indexed by (scenario, slr_quantile, return_period)."""
    key = lambda c: (c["scenario"], c["slr_quantile"], int(c["return_period"]))  # noqa: E731
    return {
        "margins_cm": [{**c, "margin_cm": int(round(100 * (onset_mpd - float(levels.loc[key(c)]))))} for c in cases],
        "reached": [{**c, "reached": bool(flooded.loc[key(c)])} for c in reach_cases]}


def value_rank(values: pd.Series, no: int) -> tuple[int, list]:
    """1-based rank of asset `no` by value (highest = 1) and the valuation nos. ranked above it."""
    v = values.dropna().sort_values(ascending=False, kind="stable")
    pos = list(v.index).index(no)
    return pos + 1, [int(x) for x in v.index[:pos]]


def lowest_flood_rp(exp: pd.DataFrame, case: str) -> pd.DataFrame:
    """Lowest return period (yr) that floods each asset, per scenario, median SLR; NaN = not within 200 yr."""
    e = exp[(exp.slr_quantile == "median") & exp[f"flooded_{case}"]]
    return e.groupby(["valuation_no", "scenario"]).return_period.min().rename(f"rp_{case}").reset_index()


def rain_band(score: pd.Series) -> pd.Series:
    """Percentile band of the continuous rain score: 'top 10%', 'top 25%' or 'other' (score itself not exported)."""
    pct = score.rank(pct=True, method="max", ascending=False)
    return pd.Series(np.where(pct <= 0.10, "top 10%", np.where(pct <= 0.25, "top 25%", "other")), index=score.index)


def forbidden_hits(obj, path: str = "") -> list[str]:
    """Paths of forbidden keys anywhere in a JSON-like object."""
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in FORBIDDEN_KEYS:
                hits.append(f"{path}/{k}")
            hits += forbidden_hits(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits += forbidden_hits(v, f"{path}[{i}]")
    return hits


def display_name(name: str) -> str:
    """Asset name as shown on the site: whitespace collapsed and the valuation sheet's trailing footnote mark dropped
    (decision 2026-10-08: "Car Park within Wang Fuk Court*" marks a valuation-basis footnote in Link's report; the site
    publishes no valuations, so the mark has no meaning there)."""
    return " ".join(str(name).split()).rstrip("*").strip()


# raw asset name -> display name, filled in main(); applied to exact string matches in every written file
DISPLAY: dict[str, str] = {}


def _names(obj):
    if isinstance(obj, dict):
        return {k: _names(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_names(v) for v in obj]
    return DISPLAY.get(obj, obj) if isinstance(obj, str) else obj


def key_paths(obj, keys, path: str = "") -> list[str]:
    """Paths of the given keys anywhere in a JSON-like object."""
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in keys:
                hits.append(f"{path}/{k}")
            hits += key_paths(v, keys, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits += key_paths(v, keys, f"{path}[{i}]")
    return hits


def level_keys(obj, path: str = "") -> list[str]:
    """Paths of keys that look like absolute heights (*_mpd, *_mcd, *_mpd_*) other than LEVEL_KEY_ALLOW."""
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k not in LEVEL_KEY_ALLOW and any(t in k.lower() for t in ("mpd", "mcd")):
                hits.append(f"{path}/{k}")
            hits += level_keys(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits += level_keys(v, f"{path}[{i}]")
    return hits


def _clean(v):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return None if np.isnan(v) else float(v)
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def round_coords(geom: dict, nd: int = 6) -> dict:
    """GeoJSON geometry with coordinates rounded to nd decimals (6 = ~0.1 m)."""
    def r(c):
        return [round(c[0], nd), round(c[1], nd)] if isinstance(c[0], (int, float)) else [r(x) for x in c]
    return {"type": geom["type"], "coordinates": r(list(geom["coordinates"]))}


def write_json(name: str, obj) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    obj = _names(json.loads(json.dumps(obj, default=_clean)))
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1))


def write_geojson(name: str, gdf: gpd.GeoDataFrame, nd: int = 6) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    gdf = gdf.to_crs(4326)
    feats = []
    for r in gdf.itertuples(index=False):
        props = {k: _clean(getattr(r, k)) for k in gdf.columns if k != "geometry"}
        props = {k: (json.loads(v) if isinstance(v, str) and v[:1] in ("[", "{") and len(v) > 1 else v) for k, v in props.items()}
        geom = round_coords(mapping(r.geometry), nd)
        feats.append({"type": "Feature", "properties": _names(props), "geometry": geom})
    (OUT / name).write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False))


def main() -> None:
    cfg_a, cfg_s = load_config("assumptions"), load_config("scenarios")
    pts = gpd.read_file(INTERIM / "assets.geojson")
    fps = gpd.read_file(INTERIM / "asset_footprints.geojson")
    vals = pd.read_csv(INTERIM / "asset_values.csv").set_index("valuation_no")
    exp = pd.read_parquet(PROC / "exposure.parquet")
    ranking = pd.read_csv(PROC / "ranking.csv")
    hot = pd.read_csv(PROC / "hotspots.csv")
    rain = pd.read_csv(HAZ / "rain_assets.csv").drop_duplicates("valuation_no").set_index("valuation_no")
    ls = pd.read_csv(HAZ / "landslide_assets.csv").drop_duplicates("valuation_no").set_index("valuation_no")
    DISPLAY.update({str(n): display_name(n) for n in pd.concat([pts.name, fps.name, vals.name]).dropna().unique()
                    if display_name(n) != str(n)})

    # --- assets: one point per asset (first accepted point), results per scenario
    p = pts.sort_values("valuation_no").drop_duplicates("valuation_no")[["valuation_no", "name", "geometry"]].copy()
    f = fps.set_index("valuation_no")
    p["district"] = p.valuation_no.map(f.district).fillna("").str.title().str.replace(" District", "")
    p["location_approximate"] = p.valuation_no.map(f.footprint_method).ne("ib1000_footprint")
    p["under_development"] = p.valuation_no.map(vals.status).eq("under_development")
    imp = pd.read_csv(PROC / "impact.csv")
    im = imp[(imp.slr_quantile == "median") & (imp.case == "central")]
    # any modelled coastal loss (direct + BI, mid cost); same basis as portfolio n_assets_with_coastal_loss
    any_loss = (im.eal_direct_hkd_mid + im.eal_bi_hkd.fillna(0)) > 0
    has_loss = {(int(n), s) for n, s in zip(im.valuation_no[any_loss], im.scenario[any_loss])}
    rp = lowest_flood_rp(exp, "central")
    for c in ("onset_low", "onset_high"):
        rp = rp.merge(lowest_flood_rp(exp, c), on=["valuation_no", "scenario"], how="outer")
    band = rain_band(rain.rain_score_cont)
    p["rain_class"] = p.valuation_no.map(rain.rain_class)
    p["rain_band"] = p.valuation_no.map(band)
    p["landslide_class"] = p.valuation_no.map(ls.landslide_class)
    per = []
    for no in p.valuation_no:
        d = {}
        for s in SCENARIOS:
            r = rp[(rp.valuation_no == no) & (rp.scenario == s)]
            g = lambda c: (int(r[c].iloc[0]) if len(r) and pd.notna(r[c].iloc[0]) else None)  # noqa: E731
            rk = ranking[(ranking.valuation_no == no) & (ranking.scenario == s)].set_index("lens")
            tier = lambda lens: (rk.loc[lens, "tier"] if lens in rk.index and isinstance(rk.loc[lens, "tier"], str)  # noqa: E731
                                 else None)
            h = hot[(hot.valuation_no == no) & (hot.scenario == s)]
            d[s] = {"rp": g("rp_central"),
                    # onset -0.15 m floods earlier (lower RP), +0.15 m later
                    "rp_range": [g("rp_onset_low"), g("rp_onset_high")],
                    "has_coastal_loss": (no, s) in has_loss,
                    "tier_absolute": tier("absolute"), "tier_relative": tier("relative"),
                    "watch": sorted(h.loc[h.asset_to_watch, "hazard"].tolist()),
                    "hotspot": {r.hazard: int(r.hazard_rank) for r in h.itertuples()}}
        per.append(json.dumps(d))
    p["scenarios"] = per
    p["relative_excluded"] = p.valuation_no.isin(cfg_a["ranking"]["relative_exclude_valuation_nos"])
    write_geojson("assets.geojson", gpd.GeoDataFrame(p, geometry="geometry", crs=pts.crs))

    # --- footprints (iB1000-derived; attribution on the map and sources page)
    fp = fps[fps.footprint_method == "ib1000_footprint"][["valuation_no", "name", "geometry"]].copy()
    fp["geometry"] = fp.geometry.simplify(0.5)
    write_geojson("footprints.geojson", gpd.GeoDataFrame(fp, geometry="geometry", crs=fps.crs))

    # --- HLC points, attributes unaltered, reprojected only
    hlc = gpd.read_file(ROOT / "data" / "raw" / "geo_landslide" / "HLC_1924-2019.gdb", layer="HLC")
    write_geojson("hlc.geojson", hlc)

    # --- raise-the-sea extents (5 m DTM bathtub, whole metres; 5 decimals = ~1 m, below the 10 m simplification)
    ext = gpd.read_file(HAZ / "flood_extents.gpkg")
    ext = ext[ext.geometry.notna()][["pass_m", "geometry"]].sort_values("pass_m")
    write_geojson("flood_extents.geojson", gpd.GeoDataFrame(ext, geometry="geometry", crs=ext.crs), nd=5)

    # --- portfolio
    port = pd.read_csv(PROC / "impact_portfolio.csv")
    pm = port[(port.slr_quantile == "median") & (port.case == "central")].set_index("scenario")
    out = {"scenarios": {}, "labels": SCENARIO_LABELS}
    for s in SCENARIOS:
        r = pm.loc[s]
        lo = r.eal_direct_hkd_mid + r.eal_bi_half_hkd
        hi = r.eal_direct_tail_hkd_mid + r.eal_bi_tail_hkd
        g = imp[(imp.scenario == s) & (imp.slr_quantile == "median") & (imp.case == "central")].set_index("valuation_no")
        t = g.eal_direct_hkd_mid + g.eal_bi_hkd.fillna(0)
        th = g.eal_direct_tail_hkd_mid + g.eal_bi_tail_hkd.fillna(0)
        # the three largest coastal EALs (truncated, full Hazus days; decision 2026-10-08, replaces the fixed
        # {129, 128, 126}); their share on that basis and, same assets, on the with-tail basis
        top3_nos, top3, top3_tail = top_share(t, 3, th)
        out["scenarios"][s] = {
            "eal_total_hkd": money_range(lo, hi),
            "eal_direct_hkd": money_range(r.eal_direct_hkd_mid, r.eal_direct_tail_hkd_mid),
            "eal_bi_hkd": money_range(r.eal_bi_half_hkd, r.eal_bi_tail_hkd),
            "share_of_net_income_pct": [sig(100 * lo / r.hk_net_passing_income_hkd), sig(100 * hi / r.hk_net_passing_income_hkd)],
            "n_assets_with_coastal_loss": int((t > 0).sum()),
            "top3_share_pct": sorted([sig(top3_tail), sig(top3)]) if top3 else None,
            "top3_valuation_nos": top3_nos,
            "top3_names": [str(g.loc[n, "name"]) for n in top3_nos] if "name" in g else None}
        # reached by water within 200 years (median, central) and reached without modelled loss; assets to watch
        reached = set(rp[(rp.scenario == s) & rp.rp_central.notna()].valuation_no.astype(int))
        losers = {n for n, sc in has_loss if sc == s}
        names = p.set_index("valuation_no").name
        hs = hot[(hot.scenario == s) & hot.asset_to_watch]
        out["scenarios"][s].update({
            "n_assets_reached": len(reached),
            "reached_no_loss_names": sorted(str(names[n]) for n in reached - losers),
            "assets_to_watch": {h: sorted(g_.name.astype(str)) for h, g_ in hs.groupby("hazard")}})
    obs = pd.read_csv(PROC / "impact_observed_summary.csv").set_index("event")
    out["mangkhut_modelled_loss_hkd"] = sig(obs.loc["mangkhut_2018", "total_hkd"])
    out["n_assets"] = int((~p.under_development).sum())
    out["n_assets_total"] = int(len(p))
    # return period 1995-2014 vs 2050 (SSP2-4.5) for every asset reached in either (Insights dumbbell; same as assets.geojson)
    rpc = rp.pivot_table(index="valuation_no", columns="scenario", values="rp_central")
    both = rpc[["baseline", "ssp245_2050"]].dropna(how="all") if {"baseline", "ssp245_2050"} <= set(rpc.columns) else rpc.iloc[0:0]
    nm = p.set_index("valuation_no").name
    out["reached_rp"] = [{"valuation_no": int(n), "name": str(nm[n]),
                          "baseline": None if pd.isna(r.baseline) else int(r.baseline),
                          "ssp245_2050": None if pd.isna(r.ssp245_2050) else int(r.ssp245_2050)} for n, r in both.iterrows()]
    out["n_footprints"] = int(fps[fps.footprint_method == "ib1000_footprint"].valuation_no.nunique())
    out["under_development_names"] = sorted(p[p.under_development].name.astype(str))
    write_json("portfolio.json", out)

    # --- adaptation (top coastal assets; ranges only)
    ad = pd.read_csv(PROC / "adaptation.csv")
    q = ad[ad.status.str.startswith("quantified")]
    ih = im[im.scenario == "ssp245_2050"].set_index("valuation_no")
    rows = {}
    for r in q.itertuples():
        e = ih.loc[r.valuation_no]
        a = rows.setdefault(r.valuation_no, {"valuation_no": r.valuation_no, "name": r.name,
                                             "eal_hkd": money_range(e.eal_direct_hkd_mid + e.eal_bi_half_hkd,
                                                                    e.eal_direct_tail_hkd_mid + e.eal_bi_tail_hkd),
                                             "barriers": {}})
        a["barriers"][f"{r.barrier_height_m:g}"] = {
            "central_hkd": money_range(r.breakeven_central_bi50_r4_hkd, r.breakeven_central_base_r4_hkd),
            "upper_hkd": money_range(r.breakeven_upper_bi50_r4_hkd, r.breakeven_upper_base_r4_hkd)}
    tot = {}
    for h in q.barrier_height_m.unique():
        g = q[q.barrier_height_m == h]
        tot[f"{h:g}"] = {"central_hkd": money_range(g.breakeven_central_bi50_r4_hkd.sum(), g.breakeven_central_base_r4_hkd.sum()),
                         "upper_hkd": money_range(g.breakeven_upper_bi50_r4_hkd.sum(), g.breakeven_upper_base_r4_hkd.sum())}
    rd = ad[~ad.status.str.startswith("quantified")]
    write_json("adaptation.json", {
        "discount_rate": 0.04, "horizon_years": 25, "scenario": "ssp245_2050",
        "assets": list(rows.values()), "totals": tot,
        "rain_driven": [{"valuation_no": int(r.valuation_no), "name": r.name} for r in rd.itertuples()]})

    # --- margin facts for named assets (cm only; decision 2026-10-08)
    se = cfg_a["site_export"]
    if not (set(se["margin_assets"]) <= MARGIN_EXCEPTION["assets"]
            and {e["valuation_no"] for e in se["event_assets"]} <= MARGIN_EXCEPTION["events"]):
        raise ValueError("site_export lists an asset outside the margins exception (decision 2026-10-08)")
    onset = pd.read_csv(HAZ / "coastal_onset.csv").set_index("valuation_no")
    lv = pd.read_csv(HAZ / "coastal_levels.csv")
    ex_ = exp.set_index(["valuation_no", "scenario", "slr_quantile", "return_period"]).flooded_central
    out_m = []
    for no in se["margin_assets"]:
        levels = lv[lv.valuation_no == no].set_index(["scenario", "slr_quantile", "return_period"]).level_mpd
        f = margin_facts(float(onset.loc[no, "onset_level_mpd"]), levels, ex_.loc[no], se["margin_cases"], se["reach_cases"])
        rank, above = value_rank(vals.value_hkd, no)
        out_m.append({"valuation_no": int(no), "name": str(vals.loc[no, "name"]), "onset_basis": str(onset.loc[no, "onset_source"]),
                      "value_rank_hk": rank, "valued_above": [str(vals.loc[n, "name"]) for n in above], **f})
    fpi = fps.drop_duplicates("valuation_no").set_index("valuation_no")
    evx = pd.read_parquet(PROC / "event_exposure.parquet")
    out_e = []
    for e in se["event_assets"]:
        no = e["valuation_no"]
        r = evx[(evx.valuation_no == no) & (evx.scenario == e["event"])].iloc[0]
        lvl, entry, floor = float(r.event_level_mpd), float(fpi.loc[no, "entry_level_mpd"]), float(fpi.loc[no, "lowest_floor_mpd"])
        out_e.append({"valuation_no": int(no), "name": str(fpi.loc[no, "name"]), "event": e["event"], "gauge_name": e["gauge_name"],
                      "observed_peak_mcd": cfg_a["event_check"]["max_sea_level_mcd"][e["event"]][e["station"]],
                      "peak_source": e["source"], "above_entry_cm": int(round(100 * (lvl - entry))),
                      "below_floor_cm": int(round(100 * (floor - lvl))), "flooded": bool(r.flooded_central)})
    write_json("margins.json", {"rule": "onset minus still-water level, whole cm; negative = exceeded", "assets": out_m,
                                "events": out_e})

    # --- scorecard
    sc = pd.read_csv(ROOT / "data" / "manual" / "audit_scores.csv")
    write_json("scorecard.json", {"total": int(sc.score.sum()), "max": int(sc.max_score.sum()),
                                  "items": sc.to_dict(orient="records")})

    # --- heat: a few cited figures and the illustrative what-if range (no HKO table)
    hw = pd.read_csv(PROC / "heat_whatif.csv").set_index("demand_change")
    write_json("heat.json", {
        "very_hot_days_baseline": cfg_s["baseline"]["very_hot_days"]["mean"],
        "very_hot_days_ssp245_2050": cfg_s["ssp245_2050"]["very_hot_days"]["mean"],
        "hot_nights_baseline": cfg_s["baseline"]["hot_nights"]["mean"],
        "hot_nights_ssp245_2050": cfg_s["ssp245_2050"]["hot_nights"]["mean"],
        "whatif_extra_cost_hkd": money_range(hw.loc[0.1, "extra_cost_hkd"], hw.loc[0.2, "extra_cost_hkd"]),
        "whatif_label": "illustrative, not a projection"})

    # --- terrain tiles (LandsD 5 m DTM, terrarium PNG; decision 2026-10-08)
    from pipeline.terrain_tiles import write_tiles
    tt = cfg_a["terrain_tiles"]
    shutil.rmtree(OUT / TERRAIN_DIR, ignore_errors=True)
    n_tiles = write_tiles(OUT / TERRAIN_DIR, *tt["zooms"])

    write_json("meta.json", {"scenarios": SCENARIOS, "labels": SCENARIO_LABELS, "headline_scenario": HEADLINE_SCENARIO,
                             "return_periods": [2, 5, 10, 20, 50, 100, 200],
                             # method parameters quoted on the site (our config, not third-party data)
                             "method": {"onset_accuracy_m": cfg_a["coastal"]["lidar_vertical_accuracy_m"],
                                        "bi_days_factor_low": cfg_a["business_interruption"]["days_factor_sensitivity"],
                                        "eal_return_periods": [2, 200],
                                        "ranking_weights": cfg_a["ranking_weights"],
                                        "weight_variants": len(cfg_a["ranking"]["weight_test_factors"]) ** 3,
                                        "tier1_min_survival": cfg_a["ranking"]["tier1_min_survival"],
                                        "top_n": cfg_a["ranking"]["top_n"], "hotspot_top_n": cfg_a["ranking"]["hotspot_top_n"],
                                        "barrier_heights_m": cfg_a["adaptation"]["barrier_heights_m"],
                                        "discount_rates": cfg_a["adaptation"]["discount_rates"],
                                        "horizon_years": cfg_a["adaptation"]["horizon_years"],
                                        "n_location_approximate": int(p.location_approximate.sum()),
                                        "share_rounding": "2 significant figures, no decimals"},
                             "terrain": {"tiles": f"{TERRAIN_DIR}/{{z}}/{{x}}/{{y}}.png", "encoding": "terrarium",
                                         "minzoom": tt["zooms"][0], "maxzoom": tt["zooms"][1], "n_tiles": n_tiles,
                                         "attribution": tt["attribution"]}})
    bad = {n: forbidden_hits(json.loads((OUT / n).read_text())) for n in [x.name for x in OUT.iterdir() if x.is_file()]}
    bad = {k: v for k, v in bad.items() if v}
    if bad:
        raise ValueError(f"forbidden fields in export: {bad}")
    print("wrote", ", ".join(sorted(x.name for x in OUT.iterdir())))


if __name__ == "__main__":
    main()
