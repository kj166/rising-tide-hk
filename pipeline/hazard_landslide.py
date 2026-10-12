"""Landslide indicators per asset (step 3; plan 2026-10-06, decisions 2026-10-07).

Our own derived metric, labelled as such; GEO's HLC points are counted, never modified.
    slope_p90_deg / slope_max_deg   slope of the LandsD 5 m DTM (Horn 3 x 3) within
                                    landslide.slope_buffer_m of the footprint / approx circle / point
    hlc_count                       GEO Historical Landslide Catchment points within hlc_radius_m
    landslide_score / _class        slope points + HLC points (config `landslide`)
The DTM is whole metres (+/-5 m), so slope is coarse: a screening indicator, not a stability
assessment.
"""

import geopandas as gpd
import numpy as np
import pandas as pd
from rasterio import features
from rasterio.windows import Window
from rasterio.windows import transform as window_transform


def slope_deg(dem: np.ndarray, cell_m: float) -> np.ndarray:
    """Horn (3 x 3) slope in degrees; edge cells use the nearest values (padding)."""
    z = np.pad(dem.astype(float), 1, mode="edge")
    a, b, c = z[:-2, :-2], z[:-2, 1:-1], z[:-2, 2:]
    d, f = z[1:-1, :-2], z[1:-1, 2:]
    g, h, i = z[2:, :-2], z[2:, 1:-1], z[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * cell_m)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * cell_m)
    return np.degrees(np.arctan(np.hypot(dzdx, dzdy)))


def slope_stats(dtm: np.ndarray, transform, geom, nodata=None) -> tuple[float, float]:
    """(p90, max) slope in degrees of the DTM cells whose centre is inside geom (window + 1-cell
    margin so the Horn kernel sees real neighbours); NaN if none."""
    import rasterio
    minx, miny, maxx, maxy = geom.bounds
    r0, c0 = rasterio.transform.rowcol(transform, minx, maxy)
    r1, c1 = rasterio.transform.rowcol(transform, maxx, miny)
    r0, c0 = max(r0 - 1, 0), max(c0 - 1, 0)
    r1, c1 = min(r1 + 2, dtm.shape[0]), min(c1 + 2, dtm.shape[1])
    win = dtm[r0:r1, c0:c1].astype(float)
    if nodata is not None:
        win[win == nodata] = np.nan
    t = window_transform(Window(c0, r0, c1 - c0, r1 - r0), transform)
    s = slope_deg(np.nan_to_num(win, nan=np.nanmean(win) if np.isfinite(win).any() else 0.0), abs(transform.a))
    inside = features.geometry_mask([geom], win.shape, t, invert=True) & np.isfinite(win)
    v = s[inside]
    return (float(np.percentile(v, 90)), float(v.max())) if v.size else (float("nan"), float("nan"))


def hlc_count(geom, hlc: gpd.GeoDataFrame, radius_m: float) -> int:
    idx = hlc.sindex.query(geom.buffer(radius_m), predicate="intersects")
    return int(len(idx))


def landslide_score(slope_p90: float, count: int, cfg: dict) -> int:
    s = 0
    if not np.isnan(slope_p90):
        s += 2 if slope_p90 >= cfg["slope_steep_deg"] else 1 if slope_p90 >= cfg["slope_moderate_deg"] else 0
    s += 2 if count >= cfg["hlc_many"] else 1 if count >= 1 else 0
    return s


def landslide_table(regions: dict, info: pd.DataFrame, dtm: np.ndarray, transform, nodata,
                    hlc: gpd.GeoDataFrame, cfg: dict) -> pd.DataFrame:
    from pipeline.hazard_rain import score_class
    rows = []
    for a in info.itertuples():
        g = regions[a.valuation_no]
        p90, mx = slope_stats(dtm, transform, g.buffer(cfg["slope_buffer_m"]), nodata)
        n = hlc_count(g, hlc, cfg["hlc_radius_m"])
        sc = landslide_score(p90, n, cfg)
        rows.append({"valuation_no": a.valuation_no, "name": a.name, "district": a.district,
                     "shared_point": bool(a.shared_point),
                     "slope_p90_deg": round(p90, 1) if not np.isnan(p90) else None,
                     "slope_max_deg": round(mx, 1) if not np.isnan(mx) else None,
                     "hlc_count": n, "landslide_score": sc,
                     "landslide_class": score_class(sc, cfg["class_medium_min"], cfg["class_high_min"])})
    return pd.DataFrame(rows)
