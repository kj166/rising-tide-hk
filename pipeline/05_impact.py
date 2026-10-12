"""Step 5: Coastal direct loss, business interruption and EAL per asset x scenario (decision 2026-10-07).

Rain and landslide are scores only in Week 3 (option (a)); they get no HK$ here.

Inputs:
    data/processed/exposure.parquet (step 4): flooded_ / depth_ per case (central, onset_low,
        onset_high) per asset x scenario x RP x SLR quantile
    data/interim/asset_values.csv (step 2): replacement_cost_hkd_low/mid/high,
        net_passing_income_hkd (daily rent = annual net passing income / 365)
    config/assumptions.yaml: depth_damage_curve (JRC Asia commercial; values in config/local),
        business_interruption (Hazus 7.0 maximum restoration time, US default: Table 6-8 COM1 retail and
        Table 6-10 COM10 parking, days by depth bin in feet; values in config/local; null -> no BI)

Rules:
    direct loss = damage_fraction(depth) x replacement cost (low / mid / high) x exposed_share
        (step 2: 1 / n_storeys, + one storey for a basement car park; decision 2026-10-07). The JRC
        maximum damage is defined per m2 of building footprint (JRC report §5.3), so the whole-building
        loss (no exposed_share) overstates multi-storey assets; it is kept as the upper-bound
        sensitivity (direct_loss_whole_hkd_*, eal_direct_whole_*).
    BI loss = downtime days x daily rent (Hazus Eq. 6-5 form: rental income loss = FA x RENT x
        restoration time, no damage factor). Downtime = retail_income_share x COM1 days + (1 -
        retail_income_share) x COM10 days (step 2 income split; car-park-only assets get COM10 only).
        Physical use overrides (business_interruption.occupancy_by_valuation_no, decision 2026-10-07):
        car service centres 128/129 = COM3 and The Quayside 126 = COM4 for their whole income, because
        the valuation sheet books their income as "Retail" whatever the use.
        Hazus times are "maximum restoration time (Hazus 7.0, US default)", so BI is an upper bound;
        sensitivity bi_loss_half_hkd = days x business_interruption.days_factor_sensitivity (0.5).
        Excluded for business_interruption.exclude_valuation_nos (94 income uncertain, 130 not built).
    Damage-curve sensitivity: JRC EUROPE commercial (depth_damage_curve.damage_fraction_europe), mid
        cost, exposed share: direct_loss_europe_hkd_mid, eal_direct_europe(_tail)_hkd_mid.
    EAL = trapezoid over annual exceedance probability p = 1/RP between the smallest and largest RP
        (main: truncated at 200 yr; sensitivity: + L(200) x 1/200, decision 2026-10-07).
    No. 130 (under development) has no replacement cost: no loss.

Outputs:
    data/processed/impact_events.csv     asset x scenario x RP x quantile x case losses
    data/processed/impact.csv            asset x scenario x quantile x case: EAL (truncated and with
                                         tail) per cost case, direct and BI, and the 1-in-100 loss
    data/processed/impact_portfolio.csv  portfolio totals per scenario x quantile x case
    data/processed/impact_observed_events.csv   per asset x observed event (Hato, Mangkhut): HKO peak at its
                                         station, depth, direct (mid) and BI losses; stations without a
                                         reading are excluded
    data/processed/impact_observed_summary.csv  per event totals, assets excluded for no observation
    data/processed/heat_whatif.csv       heat: illustrative cooling-cost what-if, not a projection
                                         (pipeline/impact_heat.py)
"""

import math
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.config import load_config  # noqa: E402
from pipeline.impact_heat import heat_whatif  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
CASES = ["central", "onset_low", "onset_high"]
COSTS = ["low", "mid", "high"]


def eal_trapezoid(rps, losses, tail: bool = False) -> float:
    """Expected annual loss: trapezoid rule over annual exceedance probability p = 1/RP, between
    the smallest and largest return period given (no extrapolation). tail=True adds
    L(max RP) x 1/max RP (losses beyond the largest RP held at that loss)."""
    rps, losses = list(rps), list(losses)
    if len(rps) != len(losses) or len(rps) < 2:
        raise ValueError("need matching return periods and losses (at least 2)")
    if len(set(rps)) != len(rps):
        raise ValueError("duplicate return periods")
    if any(l is None or (isinstance(l, float) and math.isnan(l)) for l in losses):
        raise ValueError("loss is missing (NaN)")
    pairs = sorted(zip(rps, losses))                    # ascending RP = descending p
    p = [1.0 / r for r, _ in pairs]
    l = [float(x) for _, x in pairs]
    eal = sum((p[i] - p[i + 1]) * (l[i] + l[i + 1]) / 2 for i in range(len(p) - 1))
    if tail:
        eal += l[-1] * p[-1]
    return eal


def damage_fraction(depth, depths, fractions) -> np.ndarray:
    """Damage fraction for depth(s) in metres: linear interpolation on the curve; <= 0 or NaN -> 0;
    beyond the last depth -> the last fraction."""
    d = np.asarray(depth, dtype=float)
    f = np.interp(np.nan_to_num(d, nan=0.0), depths, fractions, left=0.0, right=fractions[-1])
    return np.where((d > 0) & ~np.isnan(d), f, 0.0)


FT_M = 0.3048  # metres per international foot (exact by definition)


def restoration_days(depth_m, bins_ft):
    """Restoration time (days) from a stepped depth-bin table in feet ([min ft, max ft, days], Hazus
    Table 6-8 shape). depth <= 0 or NaN -> 0 (the table's -4..0 ft bin, water below the first floor,
    has no counterpart in a depth-inside model). A depth on a bin edge takes the lower bin
    (min < depth <= max; ASSUMPTION, the manual does not say); beyond the last bin -> its days.
    Returns None when the table is not configured."""
    if bins_ft is None:
        return None
    pos = [b for b in bins_ft if b[1] > 0]
    d_ft = np.asarray(depth_m, dtype=float) / FT_M
    out = np.full(d_ft.shape, float(pos[-1][2]))
    for lo, hi, days in reversed(pos):
        out = np.where(d_ft <= hi, float(days), out)
    return np.where((d_ft > 0) & ~np.isnan(d_ft), out, 0.0)


def mixed_restoration_days(depth_m, retail_share, bins_retail, bins_carpark):
    """Downtime blended by income (decision 2026-10-07): retail_share x COM1 days + (1 - retail_share)
    x COM10 (parking) days. None when either table is not configured."""
    r = restoration_days(depth_m, bins_retail)
    c = restoration_days(depth_m, bins_carpark)
    if r is None or c is None:
        return None
    sh = np.asarray(retail_share, dtype=float)
    return sh * r + (1 - sh) * c


def event_losses(exp: pd.DataFrame, values: pd.DataFrame, curve: dict, bi: dict) -> pd.DataFrame:
    v = values.set_index("valuation_no")
    rows = []
    bins = bi.get("restoration_bins_ft") or {}
    occ = {int(k): t for k, t in (bi.get("occupancy_by_valuation_no") or {}).items()}
    bi_ok = all(bins.get(k) is not None for k in {"com1", "com10", *occ.values()})
    excl = set(bi.get("exclude_valuation_nos") or [])
    daily = (v.net_passing_income_hkd / 365).where(~v.index.isin(excl))
    if bi_ok:
        need = set(exp.valuation_no) - excl - set(occ)
        miss = sorted(n for n in need if pd.isna(v.retail_income_share.get(n)) and pd.notna(daily.get(n)))
        if miss:
            raise ValueError(f"retail_income_share missing for nos. {miss} (step 2 income split)")
    half = bi.get("days_factor_sensitivity")
    europe = curve.get("damage_fraction_europe")
    for case in CASES:
        e = exp[["valuation_no", "name", "scenario", "return_period", "slr_quantile",
                 f"flooded_{case}", f"depth_{case}_m"]].rename(columns={f"flooded_{case}": "flooded",
                                                                         f"depth_{case}_m": "depth_m"})
        e = e.assign(case=case)
        depth = e.depth_m.where(e.flooded, 0.0)
        frac = damage_fraction(depth, curve["depths_m"], curve["damage_fraction"])
        e["damage_fraction"] = np.round(frac, 6)
        share = e.valuation_no.map(v.exposed_share)
        for c in COSTS:
            whole = frac * e.valuation_no.map(v[f"replacement_cost_hkd_{c}"]).fillna(0.0)
            e[f"direct_loss_whole_hkd_{c}"] = whole
            e[f"direct_loss_hkd_{c}"] = whole * share.fillna(0.0)
        if europe is not None:   # gentler-curve sensitivity, mid cost, exposed share
            fe = damage_fraction(depth, curve["depths_m"], europe)
            e["direct_loss_europe_hkd_mid"] = fe * e.valuation_no.map(v.replacement_cost_hkd_mid).fillna(0.0) * share.fillna(0.0)
        else:
            e["direct_loss_europe_hkd_mid"] = np.nan
        if bi_ok:
            rs = e.valuation_no.map(v.retail_income_share).fillna(1.0)   # only excluded / no-income rows are NaN
            e["downtime_days"] = mixed_restoration_days(depth, rs, bins["com1"], bins["com10"])
            for no, table in occ.items():   # physical use: one Hazus table for the asset's whole income
                m = (e.valuation_no == no).to_numpy()
                e.loc[m, "downtime_days"] = restoration_days(depth[m], bins[table])
            e["bi_loss_hkd"] = (e.downtime_days * e.valuation_no.map(daily)).fillna(0.0)
            e["bi_loss_half_hkd"] = e.bi_loss_hkd * half if half is not None else np.nan
        else:
            e["downtime_days"] = e["bi_loss_hkd"] = e["bi_loss_half_hkd"] = np.nan
        rows.append(e)
    return pd.concat(rows, ignore_index=True)


def eal_table(ev: pd.DataFrame) -> pd.DataFrame:
    out = []
    keys = ["valuation_no", "name", "scenario", "slr_quantile", "case"]
    for k, g in ev.groupby(keys, sort=False):
        g = g.sort_values("return_period")
        row = dict(zip(keys, k))
        for c in COSTS:
            col = f"direct_loss_hkd_{c}"
            row[f"eal_direct_hkd_{c}"] = eal_trapezoid(g.return_period, g[col])
            row[f"eal_direct_tail_hkd_{c}"] = eal_trapezoid(g.return_period, g[col], tail=True)
            w = f"direct_loss_whole_hkd_{c}"
            row[f"eal_direct_whole_hkd_{c}"] = eal_trapezoid(g.return_period, g[w])
            row[f"eal_direct_whole_tail_hkd_{c}"] = eal_trapezoid(g.return_period, g[w], tail=True)
        for col, key in [("bi_loss_hkd", "eal_bi"), ("bi_loss_half_hkd", "eal_bi_half"),
                         ("direct_loss_europe_hkd_mid", "eal_direct_europe")]:
            suffix = "_hkd_mid" if key == "eal_direct_europe" else "_hkd"
            if g[col].notna().all():
                row[key + suffix] = eal_trapezoid(g.return_period, g[col])
                row[key + "_tail" + suffix] = eal_trapezoid(g.return_period, g[col], tail=True)
            else:
                row[key + suffix] = row[key + "_tail" + suffix] = np.nan
        r100 = g[g.return_period == 100]
        row["loss_100_direct_hkd_mid"] = float(r100.direct_loss_hkd_mid.iloc[0]) if len(r100) else np.nan
        row["loss_100_direct_whole_hkd_mid"] = float(r100.direct_loss_whole_hkd_mid.iloc[0]) if len(r100) else np.nan
        row["max_depth_200_m"] = float(g[g.return_period == g.return_period.max()].depth_m.iloc[0])
        out.append(row)
    return pd.DataFrame(out)


def eal_pct_of_income(eal_hkd: float, income_hkd: float) -> float:
    """EAL as a percentage of annual net passing income (Week 3 checkpoint); NaN without income."""
    return 100.0 * eal_hkd / income_hkd if income_hkd and income_hkd > 0 else float("nan")


def observed_event_summary(loss: pd.DataFrame, expo: pd.DataFrame) -> pd.DataFrame:
    """Per observed event: assets assessed (stations with a reading), assets flooded, modelled direct
    (mid cost) and BI losses (Hazus maximum days and 50% days) and totals; assets on stations with no
    reading are excluded and listed."""
    rows = []
    for ev, g in expo.groupby("scenario", sort=False):
        obs = g[g.status != "no observation"]
        l = loss[(loss.scenario == ev) & (loss.case == "central")]
        d, b, h = l.direct_loss_hkd_mid.sum(), l.bi_loss_hkd.sum(), l.bi_loss_half_hkd.sum()
        rows.append({"event": ev, "n_assets_assessed": len(obs), "n_assets_flooded": int(obs.flooded_central.sum()),
                     "n_no_observation": int((g.status == "no observation").sum()),
                     "no_observation_nos": ",".join(str(n) for n in g.loc[g.status == "no observation", "valuation_no"]),
                     "direct_hkd_mid": d, "bi_hkd": b, "bi_half_hkd": h, "total_hkd": d + b, "total_half_bi_hkd": d + h})
    return pd.DataFrame(rows)


def main() -> None:
    cfg = load_config("assumptions")
    curve, bi = cfg["depth_damage_curve"], cfg["business_interruption"]
    if curve["depths_m"] is None or curve["damage_fraction"] is None:
        raise ValueError("depth_damage_curve missing (config/local/assumptions.yaml)")
    exp = pd.read_parquet(PROC / "exposure.parquet")
    values = pd.read_csv(ROOT / "data" / "interim" / "asset_values.csv")
    ev = event_losses(exp, values, curve, bi)
    ev.to_csv(PROC / "impact_events.csv", index=False)
    eal = eal_table(ev)
    eal.to_csv(PROC / "impact.csv", index=False)
    num = [c for c in eal.columns if c.startswith(("eal_", "loss_100"))]
    port = eal.groupby(["scenario", "slr_quantile", "case"])[num].sum(min_count=1).reset_index()
    port["n_assets_eal_gt_0"] = eal.groupby(["scenario", "slr_quantile", "case"]).eal_direct_hkd_mid.apply(
        lambda s: int((s > 0).sum())).values
    # EAL as % of HK annual net passing income (assets with income; no. 130 has none), mid cost
    income = float(values.loc[values.net_passing_income_hkd.notna(), "net_passing_income_hkd"].sum())
    port["hk_net_passing_income_hkd"] = income
    for name, eal_hkd in {"eal_direct": port.eal_direct_hkd_mid, "eal_direct_tail": port.eal_direct_tail_hkd_mid,
                          "eal_bi": port.eal_bi_hkd, "eal_bi_tail": port.eal_bi_tail_hkd,
                          "eal_total": port.eal_direct_hkd_mid + port.eal_bi_hkd,
                          "eal_total_tail": port.eal_direct_tail_hkd_mid + port.eal_bi_tail_hkd}.items():
        port[f"{name}_pct_income"] = [eal_pct_of_income(v, income) for v in eal_hkd]
    port.to_csv(PROC / "impact_portfolio.csv", index=False)
    print("BI computed:", eal.eal_bi_hkd.notna().any())
    for p in ["impact_events.csv", "impact.csv", "impact_portfolio.csv"]:
        print(f"wrote data/processed/{p}")
    # observed events (Hato 2017, Mangkhut 2018): modelled loss at the HKO peak levels, baseline conditions
    expo = pd.read_parquet(PROC / "event_exposure.parquet")
    obs = expo[expo.status != "no observation"]
    eloss = event_losses(obs, values, curve, bi)
    keep = ["valuation_no", "name", "scenario", "depth_m", "damage_fraction", "direct_loss_hkd_mid", "downtime_days",
            "bi_loss_hkd", "bi_loss_half_hkd"]
    eloss[eloss.case == "central"][keep + ["case"]].merge(
        obs[["valuation_no", "scenario", "station", "event_level_mpd", "status"]], on=["valuation_no", "scenario"]
    ).to_csv(PROC / "impact_observed_events.csv", index=False)
    summ = observed_event_summary(eloss, expo)
    summ.to_csv(PROC / "impact_observed_summary.csv", index=False)
    print("wrote data/processed/impact_observed_events.csv, impact_observed_summary.csv")
    # heat: illustrative cooling-cost what-if, not a projection (pipeline/impact_heat.py)
    fps = gpd.read_file(ROOT / "data" / "interim" / "asset_footprints.geojson", ignore_geometry=True)
    heat = heat_whatif(cfg["heat_whatif"], values.merge(fps[["valuation_no", "district"]], on="valuation_no"))
    heat.to_csv(PROC / "heat_whatif.csv", index=False)
    print("wrote data/processed/heat_whatif.csv (illustrative what-if, not a projection)")


if __name__ == "__main__":
    main()
