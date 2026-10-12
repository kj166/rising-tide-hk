"""Terrain tiles for the site's 3D maps (design brief docs/DESIGN_BRIEF.md; published, decision 2026-10-08).

Reads the LandsD 5 m DTM (data/raw/dtm/dtm_5m.tif, EPSG:2326, whole metres, sea = 0; CSDI Terms of Use:
publish with attribution) and writes Web Mercator PNG tiles in Mapzen "terrarium" encoding
(elevation = R * 256 + G + B / 256 - 32768), which MapLibre GL reads as a raster-dem source
(encoding: "terrarium"). Display only: whole-metre heights, bilinear resampling, no other use.
Written by pipeline/07_export.py to site/public/data/terrain/ (export contract; zooms and attribution in config
terrain_tiles). Attribution: "Terrain derived from the LandsD 5 m Digital Terrain Model, HKSAR Government, via the
CSDI Portal".

Usage (standalone): uv run python pipeline/terrain_tiles.py [--out DIR] [--zooms 5-13]
"""

import argparse
import math
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject, transform_bounds

ROOT = Path(__file__).resolve().parent.parent
DTM = ROOT / "data" / "raw" / "dtm" / "dtm_5m.tif"
R = 6378137.0


def terrarium_rgb(elev: np.ndarray) -> np.ndarray:
    """Elevation (m) -> uint8 RGB array in terrarium encoding (1/256 m resolution)."""
    v = np.clip(np.asarray(elev, dtype=np.float64) + 32768.0, 0, 65535.996)
    r = np.floor(v / 256)
    g = np.floor(v - r * 256)
    b = np.floor((v - r * 256 - g) * 256)
    return np.stack([r, g, b], axis=-1).astype(np.uint8)


def terrarium_decode(rgb: np.ndarray) -> np.ndarray:
    rgb = rgb.astype(np.float64)
    return rgb[..., 0] * 256 + rgb[..., 1] + rgb[..., 2] / 256 - 32768


def tile_range(lon0: float, lat0: float, lon1: float, lat1: float, z: int) -> tuple[range, range]:
    """x and y tile ranges (XYZ scheme) covering a WGS84 bounding box at zoom z."""
    n = 2 ** z

    def xy(lon, lat):
        return (int((lon + 180) / 360 * n),
                int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n))
    x0, y0 = xy(lon0, lat1)
    x1, y1 = xy(lon1, lat0)
    return range(x0, x1 + 1), range(y0, y1 + 1)


def tile_bounds_3857(x: int, y: int, z: int) -> tuple[float, float, float, float]:
    """(minx, miny, maxx, maxy) of an XYZ tile in EPSG:3857 metres."""
    size = 2 * math.pi * R / 2 ** z
    minx = -math.pi * R + x * size
    maxy = math.pi * R - y * size
    return minx, maxy - size, minx + size, maxy


def write_tiles(out: Path, z0: int, z1: int, dtm_path: Path = DTM) -> int:
    """Write terrarium tiles for zooms z0..z1 covering the DTM; returns the number of tiles."""
    with rasterio.open(dtm_path) as src:
        dtm = src.read(1).astype(np.float32)
        dtm[dtm < 0] = 0          # 9,165 negative cells (known issue, NOTES): shown at sea level
        bb = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
        n = 0
        for z in range(z0, z1 + 1):
            xs, ys = tile_range(*bb, z)
            for x in xs:
                for y in ys:
                    dst = np.zeros((256, 256), dtype=np.float32)
                    reproject(dtm, dst, src_transform=src.transform, src_crs=src.crs,
                              dst_transform=from_bounds(*tile_bounds_3857(x, y, z), 256, 256),
                              dst_crs="EPSG:3857", resampling=Resampling.bilinear, dst_nodata=0)
                    p = out / str(z) / str(x) / f"{y}.png"
                    p.parent.mkdir(parents=True, exist_ok=True)
                    Image.fromarray(terrarium_rgb(dst), "RGB").save(p, optimize=True)
                    n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "site" / "public" / "data" / "terrain"))
    ap.add_argument("--zooms", default="5-13")
    a = ap.parse_args()
    z0, z1 = (int(v) for v in a.zooms.split("-"))
    print(f"wrote {write_tiles(Path(a.out), z0, z1)} tiles to {a.out}")


if __name__ == "__main__":
    main()
