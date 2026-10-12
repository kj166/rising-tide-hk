"""Raise-the-sea extents (step 3 layer 'extents'; design brief decision 2026-10-08).

Bathtub fill on the LandsD 5 m DTM: for each whole-metre still-water level h (mPD) in
flood_extents.passes_m, land cells (DTM != 0) with DTM <= h that are 4-connected to the sea seeds
(the same seeds as the coastal connectivity passes). Cells are polygonised, simplified and small parts
dropped. Illustration for the site's "raise the sea" slider only: the DTM is in whole metres (+/- 5 m
stated accuracy), has no sea walls, drains or flood gates below 5 m, and no waves; asset results never
use these polygons (they use the LiDAR onset levels).
"""

import geopandas as gpd
import numpy as np
from rasterio import features
from shapely.geometry import shape
from shapely.ops import unary_union


def land_extent(wet: np.ndarray, seeds: np.ndarray, dtm: np.ndarray) -> np.ndarray:
    """Land part of a sea-connected wet mask (step 3 connected_wet): not a sea seed and DTM != 0."""
    return wet & ~seeds & (dtm != 0)


def extent_polygons(mask: np.ndarray, transform, min_area_m2: float, simplify_m: float):
    """Polygons of the True cells of `mask`, simplified (tolerance simplify_m) and without parts or
    holes smaller than min_area_m2. Returns a (Multi)Polygon or None when nothing is left."""
    if not mask.any():
        return None
    rows, cols = np.where(mask)
    r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
    sub = mask[r0:r1, c0:c1]
    t = transform @ transform.translation(c0, r0)
    geoms = [shape(g) for g, v in features.shapes(sub.astype(np.uint8), mask=sub, transform=t) if v == 1]
    merged = unary_union(geoms)
    parts = []
    for p in getattr(merged, "geoms", [merged]):
        if p.area < min_area_m2:
            continue
        holes = [i for i in p.interiors if abs(_ring_area(i.coords)) >= min_area_m2]
        parts.append(type(p)(p.exterior.coords, [h.coords for h in holes]))
    if not parts:
        return None
    out = unary_union(parts).simplify(simplify_m, preserve_topology=True)
    return None if out.is_empty else out


def _ring_area(coords) -> float:
    """Shoelace area of a closed ring (signed)."""
    xy = np.asarray(coords)
    x, y = xy[:, 0], xy[:, 1]
    return 0.5 * float(np.dot(x[:-1], y[1:]) - np.dot(x[1:], y[:-1]))


def flood_extents(dtm: np.ndarray, transform, seeds: np.ndarray, passes: list[int], crs, wet_at,
                  min_area_m2: float = 2500.0, simplify_m: float = 10.0) -> gpd.GeoDataFrame:
    """One row per pass: pass_m, area_km2 (before simplification), geometry (EPSG of `crs`).
    wet_at(h) = sea-connected wet mask at level h (step 3 connected_wet)."""
    rows = []
    for h in sorted(passes):
        m = land_extent(wet_at(h), seeds, dtm)
        g = extent_polygons(m, transform, min_area_m2, simplify_m)
        rows.append({"pass_m": int(h), "area_km2": float(m.sum()) * abs(transform.a * transform.e) / 1e6, "geometry": g})
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=crs)
