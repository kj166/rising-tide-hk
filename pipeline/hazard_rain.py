"""Rain flooding indicators per asset (step 3, option b; decisions 2026-10-06 / 2026-10-07).

No flood model: a score from local indicators, scaled by the territory-wide HKO Rx1day change.
    dsd_*_m          distance from the footprint / approx circle / point to the nearest DSD
                     flood-prone point (any group, and per group); INTERNAL (DSD locations)
    low_spot_m       ring_median_mpd - entry_level_mpd (step 1 ring metrics)
    basement         step 2 car_park_type == 'basement'
    rain_score       proximity points + low spot + basement (config `rain`); publishable
    rain_class       low / medium / high; publishable (display)
    rain_score_cont  continuous 0-4 score (proximity decay + low-spot depth + basement); used for
                     ranking (decision 2026-10-07); publishable
    rain_index_<sc>  rain_score x (1 + Rx1day % change / 100) per scenario (HKO, config/local)
"""

import geopandas as gpd
import numpy as np
import pandas as pd

GROUP_KEYS = {"Locations Prone to Blockage": "blockage",
              "Locations with Drainage Improvement Works in Progress": "works_in_progress",
              "Coastal Low-lying or Windy Residential Areas": "coastal_lowlying"}


def dsd_points(df: pd.DataFrame, crs: str) -> gpd.GeoDataFrame:
    """DSD flood-prone points (WGS84 lon/lat) projected to `crs`, with a short group key."""
    g = gpd.GeoDataFrame(df.copy(), geometry=gpd.points_from_xy(df.lon, df.lat), crs="EPSG:4326").to_crs(crs)
    g["group_key"] = g.group.map(GROUP_KEYS)
    if g.group_key.isna().any():
        raise ValueError(f"unknown DSD group(s): {sorted(set(g.group[g.group_key.isna()]))}")
    return g


def nearest_m(geom, pts: gpd.GeoDataFrame) -> float:
    """Distance (m) from geom to the nearest point; NaN if there are none."""
    return float(pts.distance(geom).min()) if len(pts) else float("nan")


def _r(v: float):
    """Whole metres, None for NaN (a group without points)."""
    return None if np.isnan(v) else round(v)


def proximity_points(dist_m: float, near_m: float, mid_m: float) -> int:
    if np.isnan(dist_m):
        return 0
    return 2 if dist_m <= near_m else 1 if dist_m <= mid_m else 0


def rain_score(dist_m: float, low_spot_m: float, basement: bool, cfg: dict) -> int:
    s = proximity_points(dist_m, cfg["dsd_near_m"], cfg["dsd_mid_m"])
    if not np.isnan(low_spot_m) and low_spot_m >= cfg["low_spot_m"] - 1e-9:
        s += 1
    if basement:
        s += 1
    return s


def rain_score_continuous(dist_m: float, low_spot_m: float, basement: bool, cfg: dict) -> float:
    """Continuous 0-4 score for ranking: proximity 2 x max(0, 1 - d / decay), low spot
    min(1, depth / full) (negative or unknown -> 0), basement 1."""
    prox = 0.0 if np.isnan(dist_m) else 2 * max(0.0, 1 - dist_m / cfg["cont_dsd_decay_m"])
    low = 0.0 if np.isnan(low_spot_m) else min(1.0, max(0.0, low_spot_m) / cfg["cont_low_spot_full_m"])
    return prox + low + (1.0 if basement else 0.0)


def rain_scenarios(scen: dict, scenarios: list[str]) -> pd.DataFrame:
    """Rx1day change per scenario: headline value (HKO main page) and the HKO likely range
    (HKO 'more details' page, CMIP6; None for the baseline)."""
    rows = []
    for s in scenarios:
        lk = scen[s].get("rx1day_change_pct_likely") or {}
        rows.append({"scenario": s, "rx1day_change_pct": scen[s]["rx1day_change_pct"],
                     "rx1day_change_pct_likely_low": lk.get("low"), "rx1day_change_pct_likely_high": lk.get("high"),
                     "details_page_mean": lk.get("details_mean")})
    return pd.DataFrame(rows)


def score_class(score: int, medium_min: int, high_min: int) -> str:
    return "high" if score >= high_min else "medium" if score >= medium_min else "low"


def rain_table(regions: dict, info: pd.DataFrame, dsd: gpd.GeoDataFrame, cfg: dict, scen: dict,
               scenarios: list[str]) -> pd.DataFrame:
    """regions: valuation_no -> geometry (footprint, approx circle or point); info: one row per
    asset with valuation_no, name, district, entry_level_mpd, ring_median_mpd, basement,
    shared_point."""
    rows = []
    for a in info.itertuples():
        g = regions[a.valuation_no]
        d = {k: nearest_m(g, dsd[dsd.group_key == k]) for k in GROUP_KEYS.values()}
        dmin = float(np.nanmin(list(d.values()))) if any(not np.isnan(v) for v in d.values()) else float("nan")
        low = (a.ring_median_mpd - a.entry_level_mpd) if pd.notna(a.entry_level_mpd) and pd.notna(a.ring_median_mpd) else float("nan")
        sc = rain_score(dmin, low, bool(a.basement), cfg)
        row = {"valuation_no": a.valuation_no, "name": a.name, "district": a.district,
               "shared_point": bool(a.shared_point), "dsd_nearest_m": _r(dmin),
               **{f"dsd_{k}_m": _r(v) for k, v in d.items()},
               "low_spot_m": round(low, 2) if not np.isnan(low) else None, "basement": bool(a.basement),
               "rain_score": sc, "rain_class": score_class(sc, cfg["class_medium_min"], cfg["class_high_min"]),
               "rain_score_cont": round(rain_score_continuous(dmin, low, bool(a.basement), cfg), 3)}
        for s in scenarios:
            pct = scen[s]["rx1day_change_pct"]
            if pct is None:
                raise ValueError(f"rx1day_change_pct missing for {s} (config/local/scenarios.yaml)")
            row[f"rain_index_{s}"] = round(sc * (1 + pct / 100), 3)
            row[f"rain_index_cont_{s}"] = round(row["rain_score_cont"] * (1 + pct / 100), 3)
        rows.append(row)
    return pd.DataFrame(rows)
