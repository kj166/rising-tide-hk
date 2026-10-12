"""Step 4: Coastal exposure per asset x scenario x return period x SLR quantile (decision 2026-10-07).

Rain and landslide enter Week 3-4 as scores only (decision 2026-10-07, option (a)); they are not
sampled here.

Inputs:
    data/processed/hazards/coastal_levels.csv   still-water level per asset x scenario x RP x quantile
    data/processed/hazards/coastal_onset.csv    onset_level_mpd (lowest level that floods the
        asset: max(entry, LiDAR sill) or max(entry, first 5 m pass); NaN = not reached by 8 m),
        onset_low_mpd / onset_high_mpd (+/- coastal.lidar_vertical_accuracy_m, LiDAR-based only)
    data/interim/asset_footprints.geojson       entry_level_mpd, lowest_floor_mpd (min iB1000
        BASELEVEL of the final footprint; NaN for assets without a footprint)

Rules (decisions 2026-10-06 / 2026-10-07):
    flooded  = level >= onset_level_mpd and level > entry_level_mpd (onset NaN -> never)
    depth_m  = level - lowest_floor_mpd (floored at 0); assets without a footprint use the
               entry level instead (floor_source 'entry_level', ASSUMPTION)
    Sensitivity cases onset_low / onset_high: onset and entry shifted by -/+ the LiDAR accuracy
    (a systematic DEM error); the floor shifts too only when it is the entry level (iB1000
    BASELEVEL is not LiDAR). Assets whose onset is not LiDAR-based keep the central values.

Output:
    data/processed/event_exposure.parquet  observed events (Hato 2017, Mangkhut 2018): per asset the
        HKO peak at its station vs its onset level (flooded_central, depth_central_m, status)
    data/processed/approx_footprint_check.csv  approximate-circle assets whose onset level is within
        coastal.approx_footprint_check.within_m of the 200-yr SSP2-4.5 2050 median level at their
        station (candidates for hand footprints; list only)
    data/processed/exposure.parquet  one row per asset x scenario x RP x quantile with level,
        entry, onset, lowest floor, floor_source, and flooded_/depth_ per case
        (central, onset_low, onset_high)
"""

import math
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.config import load_config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
HAZ = ROOT / "data" / "processed" / "hazards"
OUT = ROOT / "data" / "processed" / "exposure.parquet"
CASES = ["central", "onset_low", "onset_high"]


def _nan(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def flooded(level: float, onset: float, entry: float) -> bool:
    """Water enters: level reaches the onset and exceeds the entry level."""
    if _nan(onset) or _nan(entry):
        return False
    return level >= onset - 1e-9 and level > entry


def depth_inside(level: float, lowest_floor: float, entry: float) -> float:
    """Depth above the lowest floor (else the entry level), floored at 0."""
    ref = entry if _nan(lowest_floor) else lowest_floor
    return max(0.0, level - ref)


def exposure_table(levels: pd.DataFrame, onset: pd.DataFrame, footprints: pd.DataFrame, acc: float) -> pd.DataFrame:
    o = onset.set_index("valuation_no")
    f = footprints.set_index("valuation_no")
    df = levels[["valuation_no", "name", "station", "scenario", "return_period", "slr_quantile", "level_mpd"]].copy()
    df["entry_level_mpd"] = df.valuation_no.map(f.entry_level_mpd)
    df["lowest_floor_mpd"] = df.valuation_no.map(f.lowest_floor_mpd)
    df["floor_source"] = df.lowest_floor_mpd.isna().map({True: "entry_level", False: "ib1000_baselevel"})
    df["onset_level_mpd"] = df.valuation_no.map(o.onset_level_mpd)
    df["onset_source"] = df.valuation_no.map(o.onset_source)
    lidar = df.onset_source.isin(["lidar_sill", "entry_level"]) & df.valuation_no.map(o.onset_low_mpd).notna()
    for case, sign in [("central", 0.0), ("onset_low", -1.0), ("onset_high", 1.0)]:
        shift = (lidar * sign * acc).astype(float)
        on, en = df.onset_level_mpd + shift, df.entry_level_mpd + shift
        fl = df.lowest_floor_mpd.where(df.floor_source == "ib1000_baselevel", en)
        df[f"flooded_{case}"] = [flooded(lv, a, b) for lv, a, b in zip(df.level_mpd, on, en)]
        df[f"depth_{case}_m"] = [round(depth_inside(lv, fz, b), 3) if w else 0.0
                                 for lv, fz, b, w in zip(df.level_mpd, fl, en, df[f"flooded_{case}"])]
    return df


def event_exposure(assets: pd.DataFrame, peaks_mcd: dict, event: str, incomplete: set, cd_below_pd_m: float) -> pd.DataFrame:
    """Exposure of each asset to an observed event (Hato 2017 / Mangkhut 2018): the HKO peak sea level
    at the asset's station (mCD -> mPD), compared with its onset level as for a scenario level (baseline
    conditions, no sea level rise). Stations without a reading: status 'no observation', not flooded
    (excluded from loss totals by the caller). Readings HKO marks incomplete are lower bounds.
    assets: valuation_no, name, station, entry_level_mpd, lowest_floor_mpd, onset_level_mpd.
    Columns flooded_/depth_ for all cases are the central values (sensitivity cases not run)."""
    rows = []
    for a in assets.itertuples():
        mcd = peaks_mcd.get(a.station)
        row = {"valuation_no": a.valuation_no, "name": a.name, "scenario": event, "return_period": 0,
               "slr_quantile": "observed", "station": a.station}
        if mcd is None:
            row.update(status="no observation", event_level_mpd=float("nan"), flooded_central=False, depth_central_m=0.0)
        else:
            lv = float(mcd) - cd_below_pd_m
            fl = flooded(lv, a.onset_level_mpd, a.entry_level_mpd)
            row.update(status="incomplete (lower bound)" if a.station in incomplete else "complete",
                       event_level_mpd=round(lv, 3), flooded_central=fl,
                       depth_central_m=round(depth_inside(lv, a.lowest_floor_mpd, a.entry_level_mpd), 3) if fl else 0.0)
        rows.append(row)
    df = pd.DataFrame(rows)
    for c in ("onset_low", "onset_high"):
        df[f"flooded_{c}"], df[f"depth_{c}_m"] = df.flooded_central, df.depth_central_m
    return df


def approx_footprint_check(footprints: pd.DataFrame, onset: pd.DataFrame, levels: pd.DataFrame,
                           scenario: str, rp: int, quantile: str, within_m: float) -> pd.DataFrame:
    """Approximate-circle assets (footprint_method point_buffer_approx) whose onset level is within
    within_m of the water level at their station for scenario x RP x quantile: candidates for a
    hand-drawn footprint (planned Week 3 item; list only)."""
    approx = set(footprints.loc[footprints.footprint_method == "point_buffer_approx", "valuation_no"])
    lv = levels[(levels.scenario == scenario) & (levels.return_period == rp) & (levels.slr_quantile == quantile)]
    df = lv[lv.valuation_no.isin(approx)][["valuation_no", "station", "level_mpd"]].merge(
        onset[["valuation_no", "onset_level_mpd"]], on="valuation_no")
    df["onset_minus_level_m"] = (df.onset_level_mpd - df.level_mpd).round(3)
    return df[df.onset_minus_level_m.abs() <= within_m + 1e-9].sort_values("onset_minus_level_m").reset_index(drop=True)


def main() -> None:
    cfg = load_config("assumptions")
    levels = pd.read_csv(HAZ / "coastal_levels.csv")
    onset = pd.read_csv(HAZ / "coastal_onset.csv")
    fp = gpd.read_file(ROOT / "data" / "interim" / "asset_footprints.geojson")
    df = exposure_table(levels, onset, pd.DataFrame(fp.drop(columns="geometry")),
                        cfg["coastal"]["lidar_vertical_accuracy_m"])
    df.to_parquet(OUT, index=False)
    chk = cfg["coastal"]["approx_footprint_check"]
    fpx = pd.DataFrame(fp.drop(columns="geometry"))
    # observed events (HKO peaks in config/local event_check): one row per asset per event
    ec, off = cfg["event_check"], cfg["datum"]["chart_datum_below_pd_m"]
    base = df[(df.scenario == "baseline") & (df.return_period == 2) & (df.slr_quantile == "median")]
    base = base[["valuation_no", "name", "station", "entry_level_mpd", "lowest_floor_mpd", "onset_level_mpd"]]
    ev = pd.concat([event_exposure(base, ec["max_sea_level_mcd"][e], e, set(ec["incomplete"].get(e, [])), off)
                    for e in ec["max_sea_level_mcd"]], ignore_index=True)
    ev.to_parquet(ROOT / "data" / "processed" / "event_exposure.parquet", index=False)
    ac = approx_footprint_check(fpx, onset, levels, chk["scenario"], chk["return_period"], chk["slr_quantile"],
                                chk["within_m"])
    ac = ac.merge(fpx[["valuation_no", "name", "entry_level_mpd", "review_status"]], on="valuation_no")
    ac.to_csv(ROOT / "data" / "processed" / "approx_footprint_check.csv", index=False)
    print(f"approx-circle assets with onset within {chk['within_m']} m of the {chk['return_period']}-yr "
          f"{chk['scenario']} level: {ac.valuation_no.tolist()} -> data/processed/approx_footprint_check.csv")
    m = df[(df.slr_quantile == "median")]
    print(f"wrote {OUT.relative_to(ROOT)} ({len(df)} rows); flooded rows (median SLR) by scenario:",
          m.groupby("scenario").flooded_central.sum().to_dict())


if __name__ == "__main__":
    main()
