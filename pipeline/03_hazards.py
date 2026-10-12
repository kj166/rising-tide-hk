"""Step 3: Build hazard layers per scenario: coastal still water (2026-10-06, 2026-10-07) and the
rain, landslide and heat indicators (2026-10-07; pipeline/hazard_rain.py, hazard_landslide.py,
hazard_heat.py; outputs rain_assets.csv, landslide_assets.csv, heat_scenarios.csv and
qa_rain.png, qa_landslide.png, qa_heat.png in data/processed/hazards/).

    uv run python pipeline/03_hazards.py                      # all layers
    uv run python pipeline/03_hazards.py --layers rain,heat   # some layers

Coastal model (decisions 2026-09-24 / 2026-10-06):
    level_mpd = extreme sea level (station, RP) + sea level rise (scenario, quantile)
                + storm surge increase (scenario, station, RP)
    1. Station per asset: the PWDM tide station (Lok On Pai dropped) with the shortest
       water path to the asset's nearest open-sea cell, on a 25 m open-sea mask from the
       LandsD 5 m DTM (sea = 0; inland water dropped; bridge decks recorded in the DTM closed
       by coastal.sea_mask_close_iterations; the largest 4-connected component). Ambiguous if the
       runner-up's path is <= coastal.station_ambiguity_ratio x the winner's, or the
       straight-line nearest station differs; material if the ambiguous candidates' baseline
       levels at coastal.station_material_rp differ by > coastal.station_material_diff_m.
       Station rule (decision 2026-10-07): Tai Po Kau (coastal.tolo_harbour_station) is
       eligible only for assets in coastal.tolo_harbour_districts (draining to Tolo Harbour,
       a semi-enclosed basin with local surge amplification); elsewhere it is never winner,
       runner-up or straight-line candidate. Material cases keep the water-path station as
       central; station_alt = their highest-level candidate (blank if the winner is highest).
       They are listed in data/interim/station_review.csv (information; no case-by-case
       review). Optional decisions in data/manual/station_overrides.csv (valuation_no,
       station, decided_by, date, evidence) replace the water-path station
       (station_method 'override').
    2. Levels per asset x scenario x RP x SLR quantile (median / low / high), plus
       level_station_high_mpd = max(level, level at station_alt): station sensitivity column,
       not a scenario.
    3. Connectivity on the 5 m DTM only (whole metres, never flood depth): pass h floods DTM
       cells <= h that are 4-connected to the sea seeds (zero-valued DTM components of at
       least coastal.connectivity_sea_min_area_ha, minus inland water). An asset is reached
       at pass h if such cells lie within coastal.connectivity_proximity_m of its footprint
       (or its approx circle). connectivity_class for level W and entry level E:
           no_level            E unknown (no. 130, point only)
           above_water_level   E >= W
           connected           E < W and reached at pass floor(W)
           uncertain           E < W, reached only at pass floor(W) + 1 (DTM resolution)
           isolated_low        E < W, not reached at floor(W) + 1 (drain backflow not modelled)
       Sea walls are not resolved; bridges in the DTM can cut channels (seeds keep the
       cut-off channel pieces).
    4. LiDAR along the route to the sea (decision 2026-10-07) for
       coastal.lidar_refine_valuation_nos: route = shortest path through the lowest 5 m pass
       that reaches the asset; corridor = route + straight line to the nearest sea seed +
       asset, buffered coastal.lidar_corridor_m; the LiDAR tiles in the corridor (listed in
       data/interim/lidar_tiles_needed_coastal.csv; the step stops if one is missing; fetch
       with scripts/fetch_terrain.py --lidar --tiles ...). LiDAR no-data filled from the 5 m
       DTM. Sill = lowest still-water level at which sea-connected LiDAR cells lie within
       coastal.lidar_proximity_m of the footprint (bisection). These assets' class in every
       row: connected if level >= sill, else isolated_low (connectivity_source
       'lidar_2020_route'). Bare earth: walls and flood gates are not resolved.

Inputs:
    data/interim/asset_footprints.geojson, assets.geojson (step 1): footprints, accepted
        points, entry_level_mpd, shared_point.
    data/raw/dtm/dtm_5m.tif
        LandsD 5 m DTM, int32 whole metres, ±5 m, sea = 0, mPD per CSDI metadata.
        Used ONLY for coarse sea-connectivity and landslide slope, never for flood
        depth at a property. Land outside Hong Kong (Shenzhen) is also 0, so it counts
        as sea here. 9,165 negative cells are a known issue (docs/internal/NOTES.md).
    data/raw/lidar_dtm_2020/<tile>/<tile>.tif
        CEDD 2020 LiDAR DTM, 0.5 m, mPD: the ground-level source for flood depth
        (decision 2026-09-24); its entry levels come from step 1.
    config/assumptions.yaml, config/scenarios.yaml via pipeline/config.py
        extreme_sea_level_mpd (PWDM Corrigendum 1/2022 Tables 3-8, 9A), tide_stations
        (PWDM Part 1 Figure 2), storm_surge_increase_m (Table 44) and sea_level_rise_m
        (HKO) are transcribed into config/local/*.yaml (gitignored).
    data/manual/station_overrides.csv (tracked): reviewer station decisions.
    data/manual_local/dsd_flood_prone_areas.csv, data/raw/geo_landslide/HLC_1924-2019.gdb:
        rain / landslide parts, not built yet (HLC publishable under GEO permission
        conditions, decision 2026-10-06).

Outputs (gitignored: data/processed/hazards/ reproduces PWDM tables per station):
    data/processed/hazards/coastal_assets.csv: one row per asset (station assignment,
        station_alt, eligible stations, water paths, ambiguity flags, connectivity per DTM
        pass, shared_point, qa_class_dtm5m vs qa_class, LiDAR sill / margin / tiles).
    data/processed/hazards/coastal_levels.csv: asset x scenario x RP x SLR quantile with
        esl_mpd, slr_m, surge_increase_m, level_mpd, station_alt, level_station_high_mpd,
        entry_level_mpd, connectivity_class, connectivity_source.
    data/processed/hazards/qa_coastal_ssp245_2050_rp100.png: QA map (checkpoint).
    data/processed/hazards/qa_lidar_<no>.png: LiDAR QA map per refined asset.
    data/interim/lidar_tiles_needed_coastal.csv: LiDAR tiles along the routes.
    data/processed/hazards/coastal_onset.csv: per asset the onset level (lowest still-water level
        that floods it: max(entry, LiDAR sill) or max(entry, first 5 m pass)), the +/-
        coastal.lidar_vertical_accuracy_m sensitivity and the lowest flooding return period per
        scenario / SLR quantile (decision 2026-10-07; LiDAR refinement also covers every asset
        with entry < coastal.lidar_refine_below_entry_mpd).
    data/processed/hazards/event_check_stations.csv, event_check_assets.csv: Hato 2017 /
        Mangkhut 2018 peaks (config event_check, mCD -> mPD), implied baseline return period per
        station, and whether each asset's station peak reaches its onset.
    data/interim/tide_stations.csv: station coordinates, snapped open-sea cell, snap
        distance (and for comparison the snap distance if Figure 2 were HK1980 geographic).
    data/interim/station_review.csv: material ambiguous assets only.
"""

import argparse
import math
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio import features
from rasterio.windows import Window
from rasterio.windows import transform as window_transform
from scipy import ndimage
from skimage.graph import MCP_Geometric

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.config import load_config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
MANUAL = ROOT / "data" / "manual"
INTERIM = ROOT / "data" / "interim"
OUT = ROOT / "data" / "processed" / "hazards"
DTM_5M = RAW / "dtm" / "dtm_5m.tif"
STATION_OVERRIDES = MANUAL / "station_overrides.csv"

STATIONS = ["quarry_bay_north_point", "tai_po_kau", "tsim_bei_tsui", "tai_o",
            "waglan_island", "ko_lau_wan", "chi_ma_wan"]
SCENARIOS = ["baseline", "ssp245_2050", "ssp585_2050", "ssp585_2100"]
QUANTILES = ["median", "low", "high"]
OVERRIDE_COLS = ["valuation_no", "station", "decided_by", "date", "evidence"]
QA_SCENARIO, QA_RP, QA_QUANTILE = "ssp245_2050", 100, "median"


# --- tide stations ------------------------------------------------------------------------

def dms_to_deg(dms) -> float:
    """[degrees, minutes, seconds] -> decimal degrees (N / E positive)."""
    d, m, s = dms
    return d + m / 60 + s / 3600


def station_table(cfg: dict, crs: str) -> pd.DataFrame:
    """Station lat/lon from config (Figure 2, PDF p. 152) projected to `crs`."""
    st = cfg["tide_stations"]
    rows = []
    for name in STATIONS:
        if st[name]["lat_dms"] is None or st[name]["lon_dms"] is None:
            raise ValueError(f"tide_stations.{name} has no coordinates (config/local/assumptions.yaml)")
        rows.append({"station": name, "lat": dms_to_deg(st[name]["lat_dms"]),
                     "lon": dms_to_deg(st[name]["lon_dms"])})
    df = pd.DataFrame(rows)
    tr = Transformer.from_crs(st["coordinate_crs"], crs, always_xy=True)
    df["easting"], df["northing"] = tr.transform(df.lon.values, df.lat.values)
    return df


# --- open-sea mask and water paths -----------------------------------------------------------

def aggregate_sea(dtm: np.ndarray, factor: int, majority: float) -> np.ndarray:
    """Coarse sea mask: a block of factor x factor DTM cells is sea when the share of its
    cells equal to 0 (DTM sea) is greater than `majority`. Trailing partial blocks dropped."""
    h, w = (dtm.shape[0] // factor) * factor, (dtm.shape[1] // factor) * factor
    share = (dtm[:h, :w] == 0).reshape(h // factor, factor, w // factor, factor).mean(axis=(1, 3))
    return share > majority


def heal_bridges(mask: np.ndarray, iterations: int, inland_rc: list[tuple[int, int]]) -> np.ndarray:
    """Drop the sea components containing an inland-water point, then close small land gaps
    (3 x 3 structure, `iterations` times): the DTM records bridge decks across channels.
    The result always contains the remaining original sea cells."""
    lab, _ = ndimage.label(mask)
    drop = {lab[r, c] for r, c in inland_rc
            if 0 <= r < mask.shape[0] and 0 <= c < mask.shape[1] and lab[r, c] > 0}
    base = mask & ~np.isin(lab, list(drop))
    if iterations <= 0:
        return base
    k = iterations + 1
    padded = np.pad(base, k, constant_values=False)
    closed = ndimage.binary_closing(padded, structure=np.ones((3, 3), bool), iterations=iterations)
    out = closed[k:-k, k:-k] | base
    inland = np.isin(lab, list(drop))
    return out & ~inland


def largest_component(mask: np.ndarray) -> np.ndarray:
    """The largest 4-connected True component of `mask`."""
    lab, n = ndimage.label(mask)
    if n == 0:
        return np.zeros_like(mask, dtype=bool)
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    return lab == sizes.argmax()


def nearest_cells(mask: np.ndarray, rows, cols) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Nearest True cell of `mask` to each (row, col) and the distance in cells."""
    dist, (ir, ic) = ndimage.distance_transform_edt(~mask, return_indices=True)
    rows, cols = np.asarray(rows), np.asarray(cols)
    return ir[rows, cols], ic[rows, cols], dist[rows, cols]


def water_path_cells(sea: np.ndarray, start: tuple[int, int]) -> np.ndarray:
    """Shortest path length (in cells, diagonal steps sqrt 2) from `start` through sea cells
    to every cell; land and unreachable cells are inf."""
    costs = np.where(sea, 1.0, np.inf)
    cum, _ = MCP_Geometric(costs, fully_connected=True).find_costs([start])
    cum[~sea] = np.inf
    return cum


def eligible_stations(districts, names: list[str], basin_station: str, basin_districts) -> list[list[str]]:
    """Stations each asset may use: the Tolo Harbour station (Tai Po Kau) only for assets in a
    Tolo Harbour district (semi-enclosed basin with local surge amplification; its levels do
    not apply outside it, decision 2026-10-07); every other station for all assets. A blank
    district is not a basin district."""
    basin = {d.upper() for d in basin_districts}
    out = []
    for d in districts:
        inside = isinstance(d, str) and d.strip().upper() in basin
        out.append([s for s in names if s != basin_station or inside])
    return out


def assign_stations(sea_rc: np.ndarray, asset_to_sea_m: np.ndarray, asset_xy: np.ndarray,
                    station_xy: np.ndarray, paths_m: dict, names: list[str], level_at_rp: dict,
                    ratio: float, material_diff_m: float, eligible: list[list[str]] | None = None
                    ) -> pd.DataFrame:
    """Water-path station per asset with ambiguity flags.

    sea_rc: (n, 2) nearest open-sea cell per asset; asset_to_sea_m: distance to it;
    paths_m: station -> grid of water-path metres from the station; level_at_rp: station ->
    baseline extreme sea level used for materiality; eligible: per asset, the stations it may
    use (default all). Winner, runner-up and straight-line nearest are all taken among the
    eligible stations. station_alt = the highest-level station (level_at_rp) among the winner
    and the candidates of a material case, blank when that is the winner itself.
    """
    rows = []
    for i in range(len(sea_rc)):
        r, c = sea_rc[i]
        ok = names if eligible is None else eligible[i]
        d = {s: asset_to_sea_m[i] + paths_m[s][r, c] for s in names}
        order = sorted(ok, key=lambda s: d[s])
        win, run = order[0], order[1]
        q = d[run] / d[win] if d[win] > 0 else math.inf
        idx = [names.index(s) for s in ok]
        straight = ok[int(np.argmin(np.hypot(*(station_xy[idx] - asset_xy[i]).T)))]
        cands, reasons = [], []
        if q <= ratio:
            cands.append(run)
            reasons.append(f"runner-up {run} path {q:.2f}x")
        if straight != win:
            if straight not in cands:
                cands.append(straight)
            reasons.append(f"straight-line nearest {straight}")
        diff = max((abs(level_at_rp[s] - level_at_rp[win]) for s in cands), default=0.0)
        material = bool(cands) and diff > material_diff_m + 1e-9
        alt = max([win, *cands], key=lambda s: level_at_rp[s]) if material else win
        row = {"station": win, "runner_up": run, "runner_up_ratio": round(q, 3),
               "straight_line_station": straight,
               "station_ambiguous": bool(cands), "station_candidates": ";".join(cands),
               "station_level_diff_m": round(diff, 3),
               "station_ambiguity_material": material,
               "station_alt": alt if alt != win else "",
               "station_ambiguity_reason": "; ".join(reasons),
               "stations_eligible": ";".join(ok)}
        row.update({f"water_path_km_{s}": round(d[s] / 1000, 3) if np.isfinite(d[s]) else np.nan
                    for s in names})
        rows.append(row)
    return pd.DataFrame(rows)


def apply_overrides(assign: pd.DataFrame, overrides: pd.DataFrame) -> pd.DataFrame:
    """Reviewer decisions replace the water-path station (station_method 'override')."""
    out = assign.copy()
    out["station_method"] = "water_path"
    bad = set(overrides.station) - set(STATIONS)
    if bad:
        raise ValueError(f"unknown station(s) in {STATION_OVERRIDES.name}: {sorted(bad)}")
    unknown = set(overrides.valuation_no) - set(out.valuation_no)
    if unknown:
        raise ValueError(f"valuation nos. in {STATION_OVERRIDES.name} not in step 1: {sorted(unknown)}")
    for o in overrides.itertuples():
        m = out.valuation_no == o.valuation_no
        out.loc[m, "station"] = o.station
        out.loc[m, "station_method"] = "override"
        if "station_alt" in out:
            out.loc[m, "station_alt"] = ""
    return out


# --- still-water levels -----------------------------------------------------------------------

def still_water_level(esl_mpd: float, slr_m: float, surge_increase_m: float) -> float:
    """Coastal still-water level, mPD = extreme sea level + SLR + storm surge increase."""
    return esl_mpd + slr_m + surge_increase_m


def surge_increase(scen: dict, station: str, rp: int) -> float:
    """Table 44 increase for a scenario (baseline: a scalar 0.0)."""
    s = scen["storm_surge_increase_m"]
    v = s if not isinstance(s, dict) else s[station][rp]
    if v is None:
        raise ValueError(f"storm_surge_increase_m missing for {station} RP {rp}")
    return float(v)


def coastal_levels(assign: pd.DataFrame, esl: dict, scenarios: dict, rps: list[int]) -> pd.DataFrame:
    """Long table: one row per asset x scenario x RP x SLR quantile. With a station_alt column,
    level_station_high_mpd = max(level at the station, level at station_alt): the station
    sensitivity (high case) for material ambiguous assets; = level_mpd otherwise."""
    def level(st, sc, scen, rp, q):
        e = esl[st][rp]
        if e is None:
            raise ValueError(f"extreme_sea_level_mpd missing for {st} RP {rp}")
        slr = scen["sea_level_rise_m"][q]
        if slr is None:
            raise ValueError(f"sea_level_rise_m.{q} missing for {sc}")
        inc = surge_increase(scen, st, rp)
        return e, slr, inc, round(still_water_level(e, slr, inc), 3)

    alts = assign["station_alt"] if "station_alt" in assign else pd.Series("", index=assign.index)
    rows = []
    for a, alt in zip(assign.itertuples(), alts.fillna("")):
        for sc in SCENARIOS:
            scen = scenarios[sc]
            lower = bool(scen.get("storm_surge_increase_is_lower_bound", False))
            for rp in rps:
                for q in QUANTILES:
                    e, slr, inc, lv = level(a.station, sc, scen, rp, q)
                    high = max(lv, level(alt, sc, scen, rp, q)[3]) if alt else lv
                    rows.append({"valuation_no": a.valuation_no, "station": a.station, "scenario": sc,
                                 "return_period": rp, "slr_quantile": q, "esl_mpd": e, "slr_m": slr,
                                 "surge_increase_m": inc, "surge_increase_lower_bound": lower,
                                 "level_mpd": lv, "station_alt": alt, "level_station_high_mpd": high})
    return pd.DataFrame(rows)


# --- connectivity (5 m DTM) ---------------------------------------------------------------------

def sea_seeds(dtm: np.ndarray, min_cells: int, inland_rc: list[tuple[int, int]]) -> np.ndarray:
    """Zero-valued (sea) 4-connected components with at least min_cells cells, minus any
    component containing an inland-water point."""
    lab, _ = ndimage.label(dtm == 0)
    sizes = np.bincount(lab.ravel())
    keep = sizes >= min_cells
    keep[0] = False
    for r, c in inland_rc:
        if 0 <= r < lab.shape[0] and 0 <= c < lab.shape[1]:
            keep[lab[r, c]] = False
    return keep[lab]


def connected_wet(dtm: np.ndarray, h: float, seeds: np.ndarray, nodata=None) -> np.ndarray:
    """Cells with DTM <= h that are 4-connected to a seed cell (bathtub fill from the sea)."""
    wet = dtm <= h
    if nodata is not None:
        wet &= dtm != nodata
    wet |= seeds
    lab, _ = ndimage.label(wet)
    hit = np.unique(lab[seeds])
    return np.isin(lab, hit[hit > 0])


def region_reached(mask: np.ndarray, transform, geom) -> bool:
    """Any True cell of `mask` under `geom` (cells whose centre is inside)."""
    minx, miny, maxx, maxy = geom.bounds
    r0, c0 = rasterio.transform.rowcol(transform, minx, maxy)
    r1, c1 = rasterio.transform.rowcol(transform, maxx, miny)
    r0, c0 = max(r0, 0), max(c0, 0)
    r1, c1 = min(r1 + 1, mask.shape[0]), min(c1 + 1, mask.shape[1])
    if r0 >= r1 or c0 >= c1:
        return False
    win_t = window_transform(Window(c0, r0, c1 - c0, r1 - r0), transform)
    inside = features.geometry_mask([geom], (r1 - r0, c1 - c0), win_t, invert=True)
    return bool((mask[r0:r1, c0:c1] & inside).any())


def connectivity_class(level: float, entry: float, reached: dict) -> str:
    """Class for still-water level `level` at an asset with entry level `entry`;
    reached = {pass h: bool}. Raises if the passes needed are not computed."""
    if entry is None or (isinstance(entry, float) and math.isnan(entry)):
        return "no_level"
    if entry >= level:
        return "above_water_level"
    p = math.floor(level)
    if p not in reached or p + 1 not in reached:
        raise ValueError(f"level {level} needs DTM passes {p} and {p + 1}; computed {sorted(reached)}")
    if reached[p]:
        return "connected"
    if reached[p + 1]:
        return "uncertain"
    return "isolated_low"


# --- LiDAR refinement along the route to the sea (decision 2026-10-07) --------------------------

def route_to_sea(dtm: np.ndarray, seeds: np.ndarray, region: np.ndarray, max_pass: int, nodata=None):
    """Lowest whole-metre DTM pass at which sea-connected wet cells reach `region` (bool mask),
    and the shortest 8-connected path through that pass's wet cells from the region to a seed
    cell: (pass, [(row, col), ...]) or (None, []) if not reached by max_pass."""
    lo = int(max(math.floor(np.nanmin(np.where(region, dtm, np.inf))), 0)) if region.any() else 0
    for hpass in range(lo, max_pass + 1):
        wet = connected_wet(dtm, hpass, seeds, nodata)
        start = wet & region
        if start.any():
            costs = np.where(wet, 1.0, np.inf)
            mcp = MCP_Geometric(costs, fully_connected=True)
            cum, _ = mcp.find_costs(list(zip(*np.nonzero(start))))
            cum = np.where(seeds, cum, np.inf)
            end = np.unravel_index(int(np.argmin(cum)), cum.shape)
            return hpass, [tuple(int(v) for v in rc) for rc in mcp.traceback(end)]
    return None, []


def reached_at(dem: np.ndarray, h: float, seeds: np.ndarray, region: np.ndarray) -> bool:
    """Sea-connected LAND cells (dem <= h, not a sea seed; NaN never wet) lie in `region`:
    sea cells inside the proximity zone do not count, so the water must cross the shore
    (e.g. a seawall crest) first."""
    wet = connected_wet(np.where(np.isnan(dem), np.inf, dem), h, seeds)
    return bool((wet & ~seeds & region).any())


def lidar_sill(dem: np.ndarray, seeds: np.ndarray, region: np.ndarray, hi: float, tol: float,
               hi_max: float) -> float | None:
    """Lowest still-water level (to `tol`) at which the sea reaches `region` on `dem`
    (bathtub fill from `seeds`, 4-connected; reached_at is monotone in h). Searches up to `hi`,
    raised by 1 m steps to hi_max; None if never reached. Only land cells count (reached_at)."""
    cells = dem[region & ~seeds & ~np.isnan(dem)]
    floor_ = float(cells.min()) if cells.size else float(np.nanmin(dem))
    while not reached_at(dem, hi, seeds, region):
        if hi >= hi_max:
            return None
        hi = min(hi + 1.0, hi_max)
    lo = floor_ - tol
    if reached_at(dem, lo, seeds, region):
        return round(lo, 2)
    while hi - lo > tol / 4:  # upper bracket within tol / 4 of the true sill, then rounded
        mid = (lo + hi) / 2
        if reached_at(dem, mid, seeds, region):
            hi = mid
        else:
            lo = mid
    return round(hi, 2)


def connectivity_class_lidar(level: float, entry: float, sill: float | None) -> str:
    """Class from a LiDAR sill: connected when the level reaches the sill, else isolated_low;
    no 'uncertain' (0.5 m LiDAR resolves the route)."""
    if entry is None or (isinstance(entry, float) and math.isnan(entry)):
        return "no_level"
    if entry >= level:
        return "above_water_level"
    if sill is not None and level >= sill:
        return "connected"
    return "isolated_low"


def onset_lidar(entry: float, sill: float | None) -> tuple[float, str]:
    """(onset level, source) for a LiDAR-refined asset: water enters when the level exceeds the
    entry level AND reaches the sill."""
    if entry is None or math.isnan(entry):
        return float("nan"), "no_level"
    if sill is None or (isinstance(sill, float) and math.isnan(sill)):
        return float("nan"), "lidar_not_reached"
    return (sill, "lidar_sill") if sill > entry else (entry, "entry_level")


def onset_dtm5m(entry: float, first_pass: int | None) -> tuple[float, str]:
    """(onset level, source) from the 5 m passes: connected needs floor(level) >= the first pass
    that reaches the asset, and level > entry."""
    if entry is None or math.isnan(entry):
        return float("nan"), "no_level"
    if first_pass is None:
        return float("nan"), "dtm_5m_not_reached"
    return (float(first_pass), "dtm_5m_pass") if first_pass > entry else (entry, "entry_level")


def lowest_flooding_rp(levels_by_rp: dict, onset: float, entry: float):
    """Smallest return period whose still-water level floods the asset (level >= onset and
    level > entry); None if none of the given RPs does (or onset unknown)."""
    if onset is None or math.isnan(onset):
        return None
    for rp in sorted(levels_by_rp):
        lv = levels_by_rp[rp]
        if lv >= onset - 1e-9 and lv > entry:
            return rp
    return None


def resample_nearest(src: np.ndarray, t_src, shape, t_dst, fill=False) -> np.ndarray:
    """Nearest-cell lookup of `src` (north-up grid t_src) at the cell centres of a finer
    north-up grid (shape, t_dst); cells outside the source get `fill`."""
    rows = np.arange(shape[0]); cols = np.arange(shape[1])
    ys = t_dst.f + (rows + 0.5) * t_dst.e
    xs = t_dst.c + (cols + 0.5) * t_dst.a
    r = np.floor((ys - t_src.f) / t_src.e).astype(int)
    c = np.floor((xs - t_src.c) / t_src.a).astype(int)
    rv = (r >= 0) & (r < src.shape[0]); cv = (c >= 0) & (c < src.shape[1])
    out = np.full(shape, fill, dtype=src.dtype)
    out[np.ix_(rv, cv)] = src[np.ix_(r[rv], c[cv])]
    return out


def geom_mask(geom, shape, transform) -> np.ndarray:
    return features.geometry_mask([geom], shape, transform, invert=True)


def sill_cells(dem: np.ndarray, seeds: np.ndarray, sill: float | None, tol: float):
    """(crossing, newly_connected): newly_connected = cells that join the sea between
    sill - tol and sill; crossing = those at sill height (>= sill - 2 tol) next to cells
    already sea-connected at sill - tol, i.e. where the water first crosses the rim. Empty
    masks when there is no sill."""
    if sill is None:
        z = np.zeros(dem.shape, bool)
        return z, z
    d = np.where(np.isnan(dem), np.inf, dem)
    before = connected_wet(d, sill - tol, seeds)
    new = connected_wet(d, sill, seeds) & ~before
    cross = new & (d >= sill - 2 * tol) & ndimage.binary_dilation(before)
    return cross, new


def qa_lidar_map(no, name, dem, t, seeds, region_geom, route_xy, wet, level, entry, sill, out: Path,
                 saddle: np.ndarray | None = None, new_at_sill: np.ndarray | None = None) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    h, w = dem.shape
    extent = [t.c, t.c + w * t.a, t.f + h * t.e, t.f]
    fig, ax = plt.subplots(figsize=(11, 9))
    im = ax.imshow(dem, extent=extent, cmap="terrain", vmin=0, vmax=max(12, (sill or 0) + 3),
                   interpolation="nearest")
    fig.colorbar(im, ax=ax, shrink=0.7, label="ground, mPD (LiDAR 2020; 5 m DTM where LiDAR has no data)")
    ax.imshow(np.ma.masked_where(~(wet & ~seeds), wet), extent=extent, cmap=ListedColormap(["#00bfff"]),
              alpha=0.8, interpolation="nearest")
    if new_at_sill is not None and new_at_sill.any():
        ax.imshow(np.ma.masked_where(~new_at_sill, new_at_sill), extent=extent,
                  cmap=ListedColormap(["#ff7f0e"]), alpha=0.45, interpolation="nearest")
    ax.imshow(np.ma.masked_where(~seeds, seeds), extent=extent, cmap=ListedColormap(["#08306b"]),
              alpha=0.6, interpolation="nearest")
    for g in getattr(region_geom, "geoms", [region_geom]):
        x, y = g.exterior.xy
        ax.plot(x, y, color="red", lw=1.5)
    if saddle is not None and saddle.any():
        rr, cc = np.nonzero(saddle)
        sx, sy = rasterio.transform.xy(t, rr, cc)
        ax.scatter(sx, sy, s=40, c="magenta", marker="x", zorder=4, label="where the water first crosses (sill)")
    if route_xy:
        rx, ry = zip(*route_xy)
        ax.plot(rx, ry, color="black", lw=1, ls="--", label="5 m DTM route to the sea")
    s = "not reached in the LiDAR corridor" if sill is None else f"{sill:.2f} mPD"
    ax.set_title(f"No. {no} {name}: LiDAR connectivity at {QA_RP}-yr {QA_SCENARIO} {QA_QUANTILE} "
                 f"= {level:.2f} mPD; entry {entry:.2f} mPD; LiDAR sill (sea reaches the asset) {s}\n"
                 f"cyan = sea-connected land at {level:.2f} mPD; orange = land that joins the sea at the sill; "
                 f"dark blue = sea seeds; red = asset",
                 fontsize=9)
    ax.legend(loc="lower left", fontsize=8)
    ax.set_xlabel("Easting (EPSG:2326)"); ax.set_ylabel("Northing (EPSG:2326)")
    fig.tight_layout(); fig.savefig(out, dpi=110); plt.close(fig)


# --- run ----------------------------------------------------------------------------------------

def asset_regions(footprints: gpd.GeoDataFrame, points: gpd.GeoDataFrame, approx_m: float) -> dict:
    """Footprint, or the approx circle (accepted points buffered approx_m) for assets
    without one; None for point-only assets."""
    out = {}
    for f in footprints.itertuples():
        if f.footprint_status == "matched":
            out[f.valuation_no] = f.geometry
        elif f.footprint_status == "no_named_seed":
            out[f.valuation_no] = points[points.valuation_no == f.valuation_no].geometry.buffer(approx_m).union_all()
        else:
            out[f.valuation_no] = None
    return out


def representative_xy(footprints: gpd.GeoDataFrame, points: gpd.GeoDataFrame) -> pd.DataFrame:
    """Footprint centroid, else the centroid of the asset's accepted point(s)."""
    rows = []
    for f in footprints.itertuples():
        g = f.geometry if f.footprint_status == "matched" else \
            points[points.valuation_no == f.valuation_no].geometry.union_all()
        c = g.centroid
        rows.append({"valuation_no": f.valuation_no, "rep_e": c.x, "rep_n": c.y})
    return pd.DataFrame(rows)


def read_overrides(path: Path = STATION_OVERRIDES) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=OVERRIDE_COLS)
    df = pd.read_csv(path, dtype={"station": str})
    missing = set(OVERRIDE_COLS) - set(df.columns)
    if missing:
        raise ValueError(f"{path.name} lacks columns {sorted(missing)}")
    return df


def qa_map(sea25: np.ndarray, t25, stations: pd.DataFrame, assets: pd.DataFrame, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colours = {"connected": "#d62728", "uncertain": "#ff7f0e", "isolated_low": "#9467bd",
               "above_water_level": "#2ca02c", "no_level": "#7f7f7f"}
    fig, ax = plt.subplots(figsize=(14, 10.5))
    h, w = sea25.shape
    left, top = t25.c, t25.f
    extent = [left, left + w * t25.a, top + h * t25.e, top]
    ax.imshow(np.where(sea25, 1.0, 0.0), extent=extent, cmap="Blues", vmin=-0.6, vmax=1.6,
              interpolation="nearest")
    st = stations.set_index("station")
    for a in assets.itertuples():
        s = st.loc[a.station]
        ax.plot([a.rep_e, s.snap_e], [a.rep_n, s.snap_n], color="0.35", lw=0.4, alpha=0.6, zorder=2)
    for cls, col in colours.items():
        sub = assets[assets.qa_class == cls]
        ax.scatter(sub.rep_e, sub.rep_n, s=28, c=col, edgecolors="k", linewidths=0.3, zorder=3,
                   label=f"{cls} ({len(sub)})")
    amb = assets[assets.station_ambiguity_material]
    ax.scatter(amb.rep_e, amb.rep_n, s=110, facecolors="none", edgecolors="k", linewidths=1.2,
               zorder=4, label=f"station choice material-ambiguous ({len(amb)})")
    ax.scatter(st.snap_e, st.snap_n, marker="*", s=260, c="gold", edgecolors="k", zorder=5)
    for name, s in st.iterrows():
        n = int((assets.station == name).sum())
        ax.annotate(f"{name} ({n})", (s.snap_e, s.snap_n), xytext=(6, 6), textcoords="offset points",
                    fontsize=9, weight="bold")
    ax.set_title(f"Coastal QA: connectivity class at {QA_RP}-year, {QA_SCENARIO}, SLR {QA_QUANTILE}; "
                 "grey lines = assigned tide station (straight line for display)", fontsize=10)
    ax.legend(loc="lower left", fontsize=8)
    ax.set_xlabel("Easting (EPSG:2326)")
    ax.set_ylabel("Northing (EPSG:2326)")
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    plt.close(fig)


ONSET_CASES = [("baseline", "median"), ("ssp245_2050", "median"), ("ssp245_2050", "high"),
               ("ssp585_2050", "median"), ("ssp585_2050", "high"), ("ssp585_2100", "median")]


def onset_table(assets: pd.DataFrame, levels: pd.DataFrame, reached: dict, lid: dict, co: dict) -> pd.DataFrame:
    """One row per asset: onset level, its source, the LiDAR accuracy sensitivity (onset +/-
    lidar_vertical_accuracy_m when the onset is LiDAR-based) and the lowest flooding return
    period per ONSET_CASES at the onset and at onset -/+ accuracy."""
    acc = co["lidar_vertical_accuracy_m"]
    passes = sorted(co["connectivity_passes_m"])
    rows = []
    for a in assets.itertuples():
        e = float(a.entry_level_mpd) if pd.notna(a.entry_level_mpd) else float("nan")
        if a.valuation_no in lid:
            o, src = onset_lidar(e, lid[a.valuation_no]["lidar_sill_mpd"])
        else:
            first = next((h for h in passes if reached[a.valuation_no][h]), None)
            o, src = onset_dtm5m(e, first)
        lidar_based = src in ("lidar_sill", "entry_level")
        lo, hi = (o - acc, o + acc) if lidar_based else (float("nan"), float("nan"))
        row = {"valuation_no": a.valuation_no, "name": a.name, "district": a.district, "station": a.station,
               "entry_level_mpd": e, "lidar_sill_mpd": lid.get(a.valuation_no, {}).get("lidar_sill_mpd"),
               "onset_level_mpd": round(o, 2) if not math.isnan(o) else None, "onset_source": src,
               # not reached by the highest 5 m pass: connected needs floor(level) >= max pass + 1
               "onset_lower_bound_mpd": max(e, passes[-1] + 1) if src == "dtm_5m_not_reached" else None,
               "onset_low_mpd": round(lo, 2) if lidar_based else None,
               "onset_high_mpd": round(hi, 2) if lidar_based else None}
        lv = levels[levels.valuation_no == a.valuation_no]
        for sc, q in ONSET_CASES:
            by_rp = dict(lv[(lv.scenario == sc) & (lv.slr_quantile == q)][["return_period", "level_mpd"]].values)
            by_rp = {int(k): v for k, v in by_rp.items()}
            # entry shifts with the DEM: compare against entry -/+ accuracy in the sensitivity
            row[f"rp_{sc}_{q}"] = lowest_flooding_rp(by_rp, o, e)
            row[f"rp_{sc}_{q}_onset_low"] = lowest_flooding_rp(by_rp, lo, e - acc) if lidar_based else None
            row[f"rp_{sc}_{q}_onset_high"] = lowest_flooding_rp(by_rp, hi, e + acc) if lidar_based else None
        rows.append(row)
    out = pd.DataFrame(rows)
    for c in [c for c in out.columns if c.startswith("rp_")]:
        out[c] = out[c].astype("Int64")
    return out


def implied_return_period(levels_by_rp: dict, level: float) -> tuple[float | None, str]:
    """Return period of a still-water level on a station's baseline curve: linear in level
    vs ln(RP) between the tabulated RPs. ('<min', '>max' outside the table, rp None.)"""
    rps = sorted(levels_by_rp)
    lv = [levels_by_rp[r] for r in rps]
    if level < lv[0]:
        return None, f"<{rps[0]}"
    if level > lv[-1]:
        return None, f">{rps[-1]}"
    for (r0, l0), (r1, l1) in zip(zip(rps, lv), zip(rps[1:], lv[1:])):
        if l0 <= level <= l1:
            f = 0.0 if l1 == l0 else (level - l0) / (l1 - l0)
            rp = math.exp(math.log(r0) + f * (math.log(r1) - math.log(r0)))
            return rp, f"{rp:.0f}"
    return None, ""


def event_check(cfg: dict, onset: pd.DataFrame, assets: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hato 2017 / Mangkhut 2018 (event_check in config): per station the observed peak (mPD)
    and its implied baseline return period; per asset whether the peak at its assigned station
    reaches the onset (level >= onset and > entry). Stations without a reading: 'no observation'."""
    from pipeline.datum import mcd_to_mpd
    ev, esl = cfg["event_check"], cfg["extreme_sea_level_mpd"]
    off = cfg["datum"]["chart_datum_below_pd_m"]
    st_rows, as_rows = [], []
    for event, peaks in ev["max_sea_level_mcd"].items():
        inc = set(ev["incomplete"].get(event, []))
        for st in STATIONS:
            mcd = peaks.get(st)
            if mcd is None:
                st_rows.append({"event": event, "station": st, "status": "no observation"})
                continue
            mpd = round(float(mcd_to_mpd(mcd, off)), 3)
            rp, label = implied_return_period({int(k): v for k, v in esl[st].items()}, mpd)
            st_rows.append({"event": event, "station": st, "max_sea_level_mcd": mcd, "max_sea_level_mpd": mpd,
                            "implied_baseline_rp": round(rp, 1) if rp else None, "implied_rp_label": label,
                            "status": "incomplete (lower bound)" if st in inc else "complete"})
        for o in onset.itertuples():
            mcd = peaks.get(o.station)
            row = {"event": event, "valuation_no": o.valuation_no, "name": o.name, "station": o.station,
                   "entry_level_mpd": o.entry_level_mpd, "onset_level_mpd": o.onset_level_mpd}
            if mcd is None:
                as_rows.append({**row, "result": "no observation"})
                continue
            mpd = float(mcd_to_mpd(mcd, off))
            reached = (pd.notna(o.onset_level_mpd) and mpd >= o.onset_level_mpd - 1e-9
                       and mpd > o.entry_level_mpd)
            res = "reached" if reached else "not reached"
            if o.station in inc:
                res += " (incomplete reading: lower bound)"
            as_rows.append({**row, "event_level_mpd": round(mpd, 3),
                            "margin_m": round(mpd - o.onset_level_mpd, 2) if pd.notna(o.onset_level_mpd) else None,
                            "result": res})
    return pd.DataFrame(st_rows), pd.DataFrame(as_rows)


def _step1():
    """pipeline/01_assets.py as a module (LiDAR tile helpers, tile index path)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("assets_01", ROOT / "pipeline" / "01_assets.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def lidar_refinement(nos, regions, names, dtm, t5, seeds, nodata, co, qa_level, entry) -> dict:
    """Routes to the sea on the 5 m DTM, LiDAR tiles along them (listed in
    data/interim/lidar_tiles_needed_coastal.csv; stops if any is not downloaded), then the LiDAR
    sill per asset and a QA map. Returns valuation_no -> result dict."""
    import pyogrio
    from shapely.geometry import LineString
    step1 = _step1()
    tile_index = pyogrio.read_dataframe(step1.TILE_INDEX, layer="TileIndex")
    win_m, max_pass = co["lidar_route_window_m"], co["lidar_route_max_pass_m"]
    routes = {}
    for no in nos:
        g = regions.get(no)
        if g is None:
            raise ValueError(f"no. {no} has no footprint or approx circle; cannot refine with LiDAR")
        minx, miny, maxx, maxy = g.bounds
        r0, c0 = rasterio.transform.rowcol(t5, minx - win_m, maxy + win_m)
        r1, c1 = rasterio.transform.rowcol(t5, maxx + win_m, miny - win_m)
        r0, c0 = max(r0, 0), max(c0, 0)
        r1, c1 = min(r1 + 1, dtm.shape[0]), min(c1 + 1, dtm.shape[1])
        tw = window_transform(Window(c0, r0, c1 - c0, r1 - r0), t5)
        dw, sw = dtm[r0:r1, c0:c1], seeds[r0:r1, c0:c1]
        reg5 = geom_mask(g.buffer(co["connectivity_proximity_m"]), dw.shape, tw)
        hpass, path = route_to_sea(dw, sw, reg5, max_pass, nodata)
        xy = [rasterio.transform.xy(tw, r, c) for r, c in path]
        corridor = g.buffer(co["lidar_corridor_m"])
        if len(xy) >= 2:
            corridor = corridor.union(LineString(xy).buffer(co["lidar_corridor_m"]))
        # plus the straight line to the nearest sea seed cell: the 5 m route can miss a lower
        # direct path the coarse DTM does not show
        if sw.any():
            dist, (ir, ic) = ndimage.distance_transform_edt(~sw, return_indices=True)
            rr, cc = np.nonzero(reg5)
            k = int(np.argmin(dist[rr, cc]))
            a_xy = rasterio.transform.xy(tw, rr[k], cc[k])
            s_xy = rasterio.transform.xy(tw, ir[rr[k], cc[k]], ic[rr[k], cc[k]])
            corridor = corridor.union(LineString([a_xy, s_xy]).buffer(co["lidar_corridor_m"]))
        sheets = sorted(tile_index[tile_index.intersects(corridor)].SHEETNO)
        routes[no] = {"route_pass": hpass, "route_xy": xy, "sheets": sheets, "corridor": corridor}

    need = sorted({s for r in routes.values() for s in r["sheets"]})
    tiles = step1.lidar_tile_name(need)
    have = [len(list(step1.LIDAR_DIR.glob(f"{t}(*/*.tif"))) == 1 for t in tiles]
    pd.DataFrame({"sheet_no": need, "tile": tiles, "have": have,
                  "for_valuation_nos": [",".join(str(n) for n, r in routes.items() if s in r["sheets"])
                                        for s in need]}).to_csv(INTERIM / "lidar_tiles_needed_coastal.csv", index=False)
    if not all(have):
        missing = [t for t, ok in zip(tiles, have) if not ok]
        raise FileNotFoundError(
            f"{len(missing)} of {len(tiles)} LiDAR tiles along the routes to the sea not downloaded; listed in "
            "data/interim/lidar_tiles_needed_coastal.csv. Run: uv run python scripts/fetch_terrain.py --lidar "
            f"--tiles {','.join(missing)}  (then --sources), and rerun.")

    out = {}
    for no, r in routes.items():
        arr, trf = step1.lidar_mosaic(r["sheets"], step1.LIDAR_DIR)
        dem = arr.astype(np.float32)
        sl = resample_nearest(seeds, t5, dem.shape, trf, fill=False)
        in_corr = geom_mask(r["corridor"], dem.shape, trf) & ~sl  # land in the corridor
        nodata_share = float(np.isnan(dem[in_corr]).mean()) if in_corr.any() else float("nan")
        d5 = np.where(dtm == nodata, np.nan, dtm).astype(np.float32) if nodata is not None else dtm.astype(np.float32)
        fill = resample_nearest(d5, t5, dem.shape, trf, fill=np.float32(np.nan))
        dem = np.where(np.isnan(dem), fill, dem)
        region = geom_mask(regions[no].buffer(co["lidar_proximity_m"]), dem.shape, trf)
        hi0 = float(r["route_pass"] + 1 if r["route_pass"] is not None else max_pass)
        sill = lidar_sill(dem, sl, region, hi0, co["lidar_sill_tolerance_m"], float(max_pass))
        wet = connected_wet(np.where(np.isnan(dem), np.inf, dem), qa_level[no], sl)
        png = OUT / f"qa_lidar_{no}.png"
        saddle, new_at_sill = sill_cells(dem, sl, sill, co["lidar_sill_tolerance_m"])
        minx, miny, maxx, maxy = r["corridor"].buffer(300).bounds
        c0, r0 = ~trf * (minx, maxy)
        c1, r1 = ~trf * (maxx, miny)
        r0, c0 = max(int(r0), 0), max(int(c0), 0)
        r1, c1 = min(int(r1) + 1, dem.shape[0]), min(int(c1) + 1, dem.shape[1])
        qa_lidar_map(no, names[no], dem[r0:r1, c0:c1], window_transform(Window(c0, r0, c1 - c0, r1 - r0), trf),
                     sl[r0:r1, c0:c1], regions[no], r["route_xy"], wet[r0:r1, c0:c1], qa_level[no],
                     entry[no], sill, png, saddle[r0:r1, c0:c1], new_at_sill[r0:r1, c0:c1])
        out[no] = {"lidar_sill_mpd": sill, "dtm5m_route_pass_m": r["route_pass"],
                   "lidar_route_tiles": ",".join(step1.lidar_tile_name(r["sheets"])),
                   "lidar_nodata_share": round(nodata_share, 3), "qa_map": png}
        print(f"LiDAR no. {no}: route pass {r['route_pass']} m, {len(r['sheets'])} tiles, "
              f"nodata {nodata_share:.1%}, sill {sill}")
        del arr, dem, wet, saddle, new_at_sill
    return out


def run(only_lidar: list[int] | None = None) -> None:
    cfg = load_config("assumptions")
    scen = load_config("scenarios")
    crs, co, rps = cfg["crs"]["analysis"], cfg["coastal"], cfg["return_periods"]
    OUT.mkdir(parents=True, exist_ok=True)

    footprints = gpd.read_file(INTERIM / "asset_footprints.geojson")
    points = gpd.read_file(INTERIM / "assets.geojson")
    footprints = footprints.sort_values("valuation_no").reset_index(drop=True)

    with rasterio.open(DTM_5M) as src:
        dtm, t5, nodata = src.read(1), src.transform, src.nodata
    factor = int(round(co["sea_mask_cell_m"] / t5.a))
    cell_m = factor * t5.a
    t25 = t5 * rasterio.Affine.scale(factor)
    inland25 = [rasterio.transform.rowcol(t25, e, n) for e, n in co["inland_water_points_e_n"]]
    sea25 = largest_component(heal_bridges(aggregate_sea(dtm, factor, co["sea_mask_majority"]),
                                           co["sea_mask_close_iterations"], inland25))

    # stations: snap to the open-sea mask; snap distance also for an HK1980-geographic reading
    stations = station_table(cfg, crs)
    sr, sc = rasterio.transform.rowcol(t25, stations.easting, stations.northing)
    nr, nc, nd = nearest_cells(sea25, sr, sc)
    stations["snap_e"], stations["snap_n"] = rasterio.transform.xy(t25, nr, nc)
    stations["snap_m"] = (nd * cell_m).round(0)
    alt = Transformer.from_crs("EPSG:4611", crs, always_xy=True)
    ae, an = alt.transform(stations.lon.values, stations.lat.values)
    ar, ac = rasterio.transform.rowcol(t25, ae, an)
    stations["snap_m_if_hk1980"] = (nearest_cells(sea25, ar, ac)[2] * cell_m).round(0)
    paths = {s.station: water_path_cells(sea25, (r, c)) * cell_m
             for s, r, c in zip(stations.itertuples(), nr, nc)}

    # assets: nearest open-sea cell, water paths, ambiguity
    rep = representative_xy(footprints, points)
    ar, ac = rasterio.transform.rowcol(t25, rep.rep_e, rep.rep_n)
    ar = np.clip(ar, 0, sea25.shape[0] - 1)
    ac = np.clip(ac, 0, sea25.shape[1] - 1)
    snr, snc, snd = nearest_cells(sea25, ar, ac)
    rep["nearest_sea_e"], rep["nearest_sea_n"] = rasterio.transform.xy(t25, snr, snc)
    rep["asset_to_sea_m"] = (snd * cell_m).round(0)
    esl = cfg["extreme_sea_level_mpd"]
    level_rp = {s: esl[s][co["station_material_rp"]] for s in STATIONS}
    eligible = eligible_stations(footprints.district, STATIONS, co["tolo_harbour_station"],
                                 co["tolo_harbour_districts"])
    assign = assign_stations(np.column_stack([snr, snc]), rep.asset_to_sea_m.values,
                             rep[["rep_e", "rep_n"]].values, stations[["easting", "northing"]].values,
                             paths, STATIONS, level_rp, co["station_ambiguity_ratio"],
                             co["station_material_diff_m"], eligible)
    assets = pd.concat([footprints[["valuation_no", "name", "district", "footprint_status",
                                    "footprint_method", "review_status", "entry_level_mpd",
                                    "shared_point"]].reset_index(drop=True), rep.drop(columns="valuation_no"),
                        assign], axis=1)
    assets["shared_point"] = assets.shared_point.astype(bool)
    assets = apply_overrides(assets, read_overrides())

    # connectivity passes on the 5 m DTM
    min_cells = int(round(co["connectivity_sea_min_area_ha"] * 1e4 / (t5.a * t5.a)))
    inland = [rasterio.transform.rowcol(t5, e, n) for e, n in co["inland_water_points_e_n"]]
    seeds = sea_seeds(dtm, min_cells, inland)
    regions = asset_regions(footprints, points, cfg["elevation"]["approx_point_buffer_m"])
    buffered = {no: (g.buffer(co["connectivity_proximity_m"]) if g is not None else None)
                for no, g in regions.items()}
    reached = {no: {} for no in regions}
    for h in co["connectivity_passes_m"]:
        mask = connected_wet(dtm, h, seeds, nodata)
        for no, g in buffered.items():
            reached[no][h] = region_reached(mask, t5, g) if g is not None else False
        print(f"DTM pass {h} m: {int(mask.sum() * t5.a * t5.a / 1e6)} km2 sea-connected; "
              f"{sum(r[h] for r in reached.values())} assets reached")
        del mask
    for h in co["connectivity_passes_m"]:
        assets[f"dtm_reached_h{h}"] = assets.valuation_no.map(lambda n: reached[n][h])

    levels = coastal_levels(assets[["valuation_no", "station", "station_alt"]], esl, scen, rps)
    entry = assets.set_index("valuation_no").entry_level_mpd
    levels["entry_level_mpd"] = levels.valuation_no.map(entry)
    levels["connectivity_class"] = [connectivity_class(lv, e, reached[n]) for lv, e, n in
                                    zip(levels.level_mpd, levels.entry_level_mpd, levels.valuation_no)]

    # LiDAR along the route to the sea (coastal.lidar_refine_valuation_nos): the sill replaces
    # the 5 m DTM passes for these assets in every row
    qa5 = levels[(levels.scenario == QA_SCENARIO) & (levels.return_period == QA_RP)
                 & (levels.slr_quantile == QA_QUANTILE)].set_index("valuation_no")
    below = assets.loc[assets.entry_level_mpd < co["lidar_refine_below_entry_mpd"], "valuation_no"]
    nos = only_lidar if only_lidar is not None else sorted(set(co["lidar_refine_valuation_nos"]) | set(below))
    names = assets.set_index("valuation_no").name
    lid = lidar_refinement(nos, regions, names, dtm, t5, seeds, nodata, co, qa5.level_mpd, entry)
    levels["connectivity_source"] = np.where(levels.valuation_no.isin(list(lid)), "lidar_2020_route", "dtm_5m")
    m = levels.valuation_no.isin(list(lid))
    levels.loc[m, "connectivity_class"] = [
        connectivity_class_lidar(lv, e, lid[n]["lidar_sill_mpd"])
        for lv, e, n in zip(levels.level_mpd[m], levels.entry_level_mpd[m], levels.valuation_no[m])]
    assets["qa_class_dtm5m"] = assets.valuation_no.map(qa5.connectivity_class)
    for col in ["lidar_sill_mpd", "dtm5m_route_pass_m", "lidar_route_tiles", "lidar_nodata_share"]:
        assets[col] = assets.valuation_no.map({n: v[col] for n, v in lid.items()})
    assets["lidar_margin_m"] = (assets.lidar_sill_mpd - assets.valuation_no.map(qa5.level_mpd)).round(2)
    onset = onset_table(assets, levels, reached, lid, co)
    rp_png = OUT / f"qa_coastal_rp_{QA_SCENARIO}.png"
    qa_layer_map(dtm, t5, assets[["valuation_no", "rep_e", "rep_n"]],
                 assets.valuation_no.map(onset.set_index("valuation_no")[f"rp_{QA_SCENARIO}_median"].map(rp_bin)),
                 f"Coastal: lowest still-water return period that floods the asset (onset level), {QA_SCENARIO}, "
                 "SLR median (candidate site map)", rp_png, colours=RP_COLOURS,
                 note="onset = max(entry level, LiDAR sill / 5 m pass); still water only, no waves (lower bound "
                      "for seafront assets)")
    ev_st, ev_as = event_check(cfg, onset, assets)
    assets["connectivity_source"] = np.where(assets.valuation_no.isin(list(lid)), "lidar_2020_route", "dtm_5m")
    levels.insert(1, "name", levels.valuation_no.map(assets.set_index("valuation_no").name))

    qa = levels[(levels.scenario == QA_SCENARIO) & (levels.return_period == QA_RP)
                & (levels.slr_quantile == QA_QUANTILE)].set_index("valuation_no")
    assets["qa_level_mpd"] = assets.valuation_no.map(qa.level_mpd)
    assets["qa_class"] = assets.valuation_no.map(qa.connectivity_class)
    assets["qa_level_station_high_mpd"] = assets.valuation_no.map(qa.level_station_high_mpd)

    # outputs
    stations.to_csv(INTERIM / "tide_stations.csv", index=False)
    assets.to_csv(OUT / "coastal_assets.csv", index=False)
    levels.to_csv(OUT / "coastal_levels.csv", index=False)
    onset.to_csv(OUT / "coastal_onset.csv", index=False)
    ev_st.to_csv(OUT / "event_check_stations.csv", index=False)
    ev_as.to_csv(OUT / "event_check_assets.csv", index=False)
    review = assets[assets.station_ambiguity_material & (assets.station_method == "water_path")]
    review = review.assign(qa_level_station_high_mpd=review.valuation_no.map(qa.level_station_high_mpd))
    review = review[["valuation_no", "name", "district", "entry_level_mpd", "station", "station_alt",
                     "qa_level_mpd", "qa_level_station_high_mpd", "station_candidates",
                     "station_level_diff_m", "station_ambiguity_reason", "runner_up", "runner_up_ratio",
                     "straight_line_station", "stations_eligible", "asset_to_sea_m"]
                    + [f"water_path_km_{s}" for s in STATIONS]].sort_values("entry_level_mpd")
    review.to_csv(INTERIM / "station_review.csv", index=False)
    if not STATION_OVERRIDES.exists():
        pd.DataFrame(columns=OVERRIDE_COLS).to_csv(STATION_OVERRIDES, index=False)
    png = OUT / f"qa_coastal_{QA_SCENARIO}_rp{QA_RP}.png"
    qa_map(sea25, t25, stations, assets, png)
    for p in [rp_png, INTERIM / "tide_stations.csv", OUT / "coastal_assets.csv", OUT / "coastal_levels.csv",
              OUT / "coastal_onset.csv", OUT / "event_check_stations.csv", OUT / "event_check_assets.csv",
              INTERIM / "station_review.csv", png]:
        print(f"wrote {p.relative_to(ROOT)}")
    summarise(stations, assets, levels, review)


def summarise(stations, assets, levels, review) -> None:
    print("\nstation snap (m):", stations.set_index("station").snap_m.to_dict())
    print("assets per station:", assets.station.value_counts().to_dict())
    print(f"ambiguous: {int(assets.station_ambiguous.sum())}; material: {int(assets.station_ambiguity_material.sum())}"
          f" (review list {len(review)})")
    print(f"class at {QA_RP}-yr {QA_SCENARIO} {QA_QUANTILE}:", assets.qa_class.value_counts().to_dict())
    med = levels[levels.slr_quantile == "median"]
    print("class counts by scenario (median SLR, RP 100):")
    print(med[med.return_period == 100].groupby("scenario").connectivity_class.value_counts().unstack(fill_value=0)
          .to_string())


# --- rain, landslide, heat (decision 2026-10-07) -------------------------------------------------

CLASS_COLOURS = {"low": "#2ca02c", "medium": "#ff7f0e", "high": "#d62728"}
RP_COLOURS = {"<=20 yr": "#7f0000", "50 yr": "#d62728", "100 yr": "#ff7f0e", "200 yr": "#ffd92f",
              "none <=200 yr": "#d9d9d9"}


def rp_bin(rp) -> str:
    """Lowest flooding return period -> map category (RPs 2-20 grouped as <=20)."""
    if rp is None or pd.isna(rp):
        return "none <=200 yr"
    rp = int(rp)
    return "<=20 yr" if rp <= 20 else f"{rp} yr"
LAYER_SCENARIOS = ["baseline", "ssp245_2050", "ssp585_2050", "ssp585_2100"]


def _hillshade(dtm: np.ndarray, factor: int) -> np.ndarray:
    d = dtm[::factor, ::factor].astype(float)
    gy, gx = np.gradient(d)
    shade = 0.5 + 0.5 * (-gx + gy) / np.sqrt(1 + gx ** 2 + gy ** 2)
    return np.where(d <= 0, np.nan, shade)


def qa_layer_map(dtm, t5, xy: pd.DataFrame, cls: pd.Series, title: str, out: Path, extra=None,
                 note: str = "", colours: dict | None = None) -> None:
    """Assets coloured by class on a 5 m DTM hillshade (50 m display); extra = list of
    (x, y, label, style dict) point sets drawn underneath."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    f = 10
    hs = _hillshade(dtm, f)
    h, w = hs.shape
    fig, ax = plt.subplots(figsize=(14, 10.5))
    ax.imshow(np.where(np.isnan(hs), 1.0, np.nan), extent=[t5.c, t5.c + w * f * t5.a, t5.f + h * f * t5.e, t5.f],
              cmap="Blues", vmin=0, vmax=2.5, interpolation="nearest")
    ax.imshow(hs, extent=[t5.c, t5.c + w * f * t5.a, t5.f + h * f * t5.e, t5.f], cmap="Greys_r", vmin=0, vmax=1.2,
              alpha=0.6, interpolation="nearest")
    for x, y, label, style in (extra or []):
        ax.scatter(x, y, label=label, zorder=2, **style)
    for c, col in (colours or CLASS_COLOURS).items():
        m = cls == c
        ax.scatter(xy.rep_e[m], xy.rep_n[m], s=34, c=col, edgecolors="k", linewidths=0.4, zorder=4,
                   label=f"{c} ({int(m.sum())})")
    ax.set_xlim(t5.c + 0.02 * w * f * t5.a, t5.c + w * f * t5.a)
    ax.set_title(title, fontsize=10)
    if note:
        ax.text(0.995, 0.005, note, transform=ax.transAxes, fontsize=7, ha="right", va="bottom")
    ax.legend(loc="lower left", fontsize=8)
    ax.set_xlabel("Easting (EPSG:2326)")
    ax.set_ylabel("Northing (EPSG:2326)")
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    plt.close(fig)


def qa_heat_chart(heat: pd.DataFrame, base: dict, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    labels = ["1995–2014"] + list(heat.scenario)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8))
    for ax, key, title in [(axes[0], "very_hot_days", "Very hot days per year"),
                           (axes[1], "hot_nights", "Hot nights per year")]:
        means = [base[key]["mean"]] + list(heat[key])
        lo = [0] + list(heat[key] - heat[f"{key}_low"])
        hi = [0] + list(heat[f"{key}_high"] - heat[key])
        ax.bar(labels, means, yerr=[lo, hi], color=["0.6"] + ["#d62728"] * len(heat), capsize=4)
        ax.set_title(title + " (bars: HKO likely range)", fontsize=9)
        ax.tick_params(axis="x", labelrotation=20, labelsize=8)
    t = list(heat.mean_temp_change_c)
    if heat.mean_temp_change_c_low.notna().all():
        err = [[0] + [m - lo for m, lo in zip(t, heat.mean_temp_change_c_low)],
               [0] + [hi - m for m, hi in zip(t, heat.mean_temp_change_c_high)]]
        title = ("Annual mean temperature change, °C vs 1995–2014\n(bars: HKO likely range from the "
                 "'more details' page, CMIP6)")
    else:
        err, title = None, "Annual mean temperature change, °C vs 1995–2014\n(HKO publishes no likely range for this variable)"
    axes[2].bar(labels, [0.0] + t, yerr=err, color=["0.6"] + ["#ff7f0e"] * len(heat), capsize=4)
    axes[2].set_title(title, fontsize=9)
    axes[2].tick_params(axis="x", labelrotation=20, labelsize=8)
    fig.suptitle("Heat (HKO projections; territory-wide, the same for every asset)", fontsize=10)
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    plt.close(fig)


def run_layers(layers: list[str]) -> None:
    import geopandas as gpd  # noqa: F811
    from pipeline.hazard_heat import heat_table
    from pipeline.hazard_landslide import landslide_table
    from pipeline.hazard_rain import dsd_points, rain_table
    cfg = load_config("assumptions")
    scen = load_config("scenarios")
    crs = cfg["crs"]["analysis"]
    OUT.mkdir(parents=True, exist_ok=True)
    footprints = gpd.read_file(INTERIM / "asset_footprints.geojson").sort_values("valuation_no").reset_index(drop=True)
    points = gpd.read_file(INTERIM / "assets.geojson")
    regions = asset_regions(footprints, points, cfg["elevation"]["approx_point_buffer_m"])
    for no, g in list(regions.items()):
        if g is None:  # point-only asset (no. 130): its accepted point(s)
            regions[no] = points[points.valuation_no == no].geometry.union_all()
    xy = representative_xy(footprints, points).set_index("valuation_no").loc[footprints.valuation_no].reset_index()
    with rasterio.open(DTM_5M) as src:
        dtm, t5, nodata = src.read(1), src.transform, src.nodata
    info = footprints[["valuation_no", "name", "district", "entry_level_mpd", "ring_median_mpd", "shared_point"]].copy()
    vals = pd.read_csv(INTERIM / "asset_values.csv").set_index("valuation_no")
    info["basement"] = info.valuation_no.map(vals.car_park_type).eq("basement")
    written = []
    if "rain" in layers:
        dsd = dsd_points(pd.read_csv(ROOT / "data" / "manual_local" / "dsd_flood_prone_areas.csv"), crs)
        rain = rain_table(regions, info, dsd, cfg["rain"], scen, LAYER_SCENARIOS)
        rain.to_csv(OUT / "rain_assets.csv", index=False)
        from pipeline.hazard_rain import rain_scenarios
        rain_scenarios(scen, LAYER_SCENARIOS).to_csv(OUT / "rain_scenarios.csv", index=False)
        written.append(OUT / "rain_scenarios.csv")
        style = {"blockage": dict(s=6, c="#1f77b4", marker="."), "works_in_progress": dict(s=14, c="#9467bd", marker="^"),
                 "coastal_lowlying": dict(s=14, c="#17becf", marker="s")}
        extra = [(dsd.geometry.x[dsd.group_key == k], dsd.geometry.y[dsd.group_key == k], f"DSD {k} ({int((dsd.group_key == k).sum())}, INTERNAL)", st)
                 for k, st in style.items()]
        png = OUT / "qa_rain.png"
        qa_layer_map(dtm, t5, xy, xy.valuation_no.map(rain.set_index("valuation_no").rain_class),
                     "Rain flooding (indicator, baseline): DSD proximity + local low spot + basement car park; "
                     "scenario index = score x HKO Rx1day change", png, extra,
                     "DSD flood-prone points: internal, not for publication")
        written += [OUT / "rain_assets.csv", png]
        print("rain classes:", rain.rain_class.value_counts().to_dict())
    if "landslide" in layers:
        hlc = gpd.read_file(RAW / "geo_landslide" / "HLC_1924-2019.gdb", layer="HLC").to_crs(crs)
        ls = landslide_table(regions, info, dtm, t5, nodata, hlc, cfg["landslide"])
        ls.to_csv(OUT / "landslide_assets.csv", index=False)
        png = OUT / "qa_landslide.png"
        qa_layer_map(dtm, t5, xy, xy.valuation_no.map(ls.set_index("valuation_no").landslide_class),
                     "Landslide (our derived screening metric, not GEO data): 5 m DTM slope p90 within 50 m + "
                     "HLC points within 200 m", png,
                     [(hlc.geometry.x, hlc.geometry.y, f"HLC points ({len(hlc)})", dict(s=3, c="#8c564b", marker="."))],
                     "Historical Landslide Catchments: Geotechnical Engineering Office, Civil Engineering and "
                     "Development Department (GEO, CEDD)")
        written += [OUT / "landslide_assets.csv", png]
        print("landslide classes:", ls.landslide_class.value_counts().to_dict())
    if "heat" in layers:
        heat = heat_table(scen, LAYER_SCENARIOS[1:])
        heat.to_csv(OUT / "heat_scenarios.csv", index=False)
        png = OUT / "qa_heat.png"
        qa_heat_chart(heat, scen["baseline"], png)
        written += [OUT / "heat_scenarios.csv", png]
        print(heat.to_string(index=False))
    if "extents" in layers:
        # raise-the-sea illustration (design brief 2026-10-08): bathtub extents on the 5 m DTM
        from pipeline.hazard_extents import flood_extents
        co, fe = cfg["coastal"], cfg["flood_extents"]
        min_cells = int(round(co["connectivity_sea_min_area_ha"] * 1e4 / (t5.a * t5.a)))
        seeds = sea_seeds(dtm, min_cells, [rasterio.transform.rowcol(t5, e, n) for e, n in co["inland_water_points_e_n"]])
        ext = flood_extents(dtm, t5, seeds, fe["passes_m"], crs, lambda h: connected_wet(dtm, h, seeds, nodata),
                            fe["min_area_m2"], fe["simplify_m"])
        ext.to_file(OUT / "flood_extents.gpkg", driver="GPKG")
        written.append(OUT / "flood_extents.gpkg")
        print(ext.drop(columns="geometry").to_string(index=False))
    for p_ in written:
        print(f"wrote {p_.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lidar-only", default="",
                        help="comma-separated valuation nos.: refine only these with LiDAR (trial runs; "
                             "the full run uses coastal.lidar_refine_valuation_nos)")
    parser.add_argument("--layers", default="coastal,rain,landslide,heat,extents",
                        help="comma-separated hazard layers to build (default: all)")
    a = parser.parse_args()
    layers = [x.strip() for x in a.layers.split(",") if x.strip()]
    bad = set(layers) - {"coastal", "rain", "landslide", "heat", "extents"}
    if bad:
        parser.error(f"unknown layer(s): {sorted(bad)}")
    if "coastal" in layers:
        run([int(x) for x in a.lidar_only.split(",") if x] or None)
    if set(layers) - {"coastal"}:
        run_layers(layers)


if __name__ == "__main__":
    main()
