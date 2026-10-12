"""Tests for pipeline/07_export.py: helpers, and the export check (decision 2026-10-08): nothing forbidden
may appear in site/public/data/ (per-asset Link inputs, relative-lens ratio, water levels, continuous rain
score, DSD points, AXA rows, transcribed third-party tables); spatial files in EPSG:4326 (lon / lat).
Site levels (decision 2026-10-12): absolute ground, entrance, floor or sill levels are never published as numbers;
return periods with their ±0.15 m range (which bound those levels) are; cm margins for The Quayside and Chai Wan Car
Service Centre only."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "public" / "data"
_spec = importlib.util.spec_from_file_location("export_07", ROOT / "pipeline" / "07_export.py")
ex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ex)


def test_sig_and_money_range():
    assert ex.sig(3575515.3) == 3600000.0
    assert ex.sig(0.0366) == 0.037
    assert ex.sig(0) == 0.0 and ex.sig(float("nan")) is None
    assert ex.money_range(23_270_000, 7_200_000) == [7_200_000.0, 23_000_000.0]


def test_rain_band_percentiles():
    s = pd.Series(np.arange(1, 21, dtype=float))          # 20 assets, 20 = highest
    b = ex.rain_band(s)
    assert list(b.iloc[-2:]) == ["top 10%", "top 10%"]     # top 2 of 20
    assert list(b.iloc[-5:-2]) == ["top 25%"] * 3          # next 3 (top 5 of 20)
    assert b.iloc[0] == "other"


def test_lowest_flood_rp():
    e = pd.DataFrame({"valuation_no": [1, 1, 1, 2], "scenario": "s", "slr_quantile": "median",
                      "return_period": [10, 50, 200, 200], "flooded_central": [False, True, True, False]})
    r = ex.lowest_flood_rp(e, "central").set_index("valuation_no")
    assert r.loc[1, "rp_central"] == 50 and 2 not in r.index


def test_top_share_picks_largest_and_shares_both_bases():
    t = pd.Series({129: 3.6, 128: 1.6, 41: 0.9, 126: 0.8, 66: 0.7, 5: 0.0})
    th = pd.Series({129: 4.3, 128: 2.6, 41: 2.7, 126: 2.4, 66: 1.0, 5: 0.0})
    nos, sh, sh_other = ex.top_share(t, 3, th)
    assert nos == [129, 128, 41]
    assert sh == pytest.approx(100 * 6.1 / 7.6) and sh_other == pytest.approx(100 * 9.6 / 13.0)
    assert ex.top_share(pd.Series({1: 0.0}), 3) == ([], None, None)


def test_margin_facts_and_value_rank():
    idx = pd.MultiIndex.from_tuples([("s", "median", 100), ("s", "high", 100), ("t", "median", 200)])
    levels = pd.Series([1.20, 1.28, 1.49], index=idx)
    flooded = pd.Series([False, False, True], index=idx)
    f = ex.margin_facts(1.29, levels, flooded,
                        [{"scenario": "s", "slr_quantile": "median", "return_period": 100},
                         {"scenario": "s", "slr_quantile": "high", "return_period": 100}],
                        [{"scenario": "t", "slr_quantile": "median", "return_period": 200}])
    assert [m["margin_cm"] for m in f["margins_cm"]] == [9, 1] and f["reached"][0]["reached"] is True
    assert ex.value_rank(pd.Series({1: 6.1, 126: 6.0, 2: 5.0}), 126) == (2, [1])


def test_forbidden_hits_finds_nested_keys():
    obj = {"a": [{"ok": 1, "net_passing_income_hkd": 5}], "b": {"rain_score_cont": 1.2}}
    assert sorted(ex.forbidden_hits(obj)) == ["/a[0]/net_passing_income_hkd", "/b/rain_score_cont"]


# --- export check on the real output (skipped until `make site` has run) -----------------------

def _files():
    if not OUT.exists() or not any(OUT.iterdir()):
        pytest.skip("site/public/data not exported yet (run make site)")
    return sorted(OUT.iterdir())


def test_export_has_no_forbidden_fields_or_files():
    for f in _files():
        if f.is_dir():
            assert f.name == ex.TERRAIN_DIR, f"unexpected directory {f.name}"   # checked in the terrain test
            continue
        assert not any(b in f.stem.lower() for b in ex.FORBIDDEN_FILES), f"forbidden file {f.name}"
        assert f.suffix in (".json", ".geojson"), f"unexpected file {f.name}"
        hits = ex.forbidden_hits(json.loads(f.read_text()))
        assert not hits, f"{f.name}: {hits}"


def test_export_assets_carry_no_per_asset_money():
    a = json.loads((OUT / "assets.geojson").read_text()) if (OUT / "assets.geojson").exists() else pytest.skip()
    for feat in a["features"]:
        flat = json.dumps(feat["properties"])
        assert "hkd" not in flat.lower(), feat["properties"]["valuation_no"]


def test_export_spatial_files_are_wgs84_in_hong_kong():
    for f in _files():
        if f.suffix != ".geojson":
            continue
        g = json.loads(f.read_text())
        xs, ys = [], []

        def walk(c):
            if isinstance(c[0], (int, float)):
                xs.append(c[0]); ys.append(c[1])
            else:
                for x in c:
                    walk(x)
        for feat in g["features"]:
            walk(feat["geometry"]["coordinates"])
        assert 113.8 < min(xs) and max(xs) < 114.5 and 22.1 < min(ys) and max(ys) < 22.6, f.name


def test_export_hlc_attributes_unaltered():
    f = OUT / "hlc.geojson"
    if not f.exists():
        pytest.skip()
    import geopandas as gpd
    raw = gpd.read_file(ROOT / "data" / "raw" / "geo_landslide" / "HLC_1924-2019.gdb", layer="HLC")
    g = json.loads(f.read_text())
    assert len(g["features"]) == len(raw)
    assert set(g["features"][0]["properties"]) == set(raw.columns) - {"geometry"}


def test_export_adaptation_only_top_coastal_assets():
    f = OUT / "adaptation.json"
    if not f.exists():
        pytest.skip()
    d = json.loads(f.read_text())
    assert len(d["assets"]) <= 10
    for a in d["assets"]:
        assert len(a["eal_hkd"]) == 2                     # ranges only


def test_export_flood_extents_contract():
    """Raise-the-sea extents (design brief 2026-10-08): pass_m only, one feature per configured
    whole-metre pass, ascending, and each extent covers the one below it (bathtub is monotone)."""
    f = OUT / "flood_extents.geojson"
    if not f.exists():
        pytest.skip()
    from shapely.geometry import shape
    from pipeline.config import load_config
    g = json.loads(f.read_text())
    passes = [feat["properties"]["pass_m"] for feat in g["features"]]
    for feat in g["features"]:
        assert set(feat["properties"]) == ex.EXTENT_KEYS
    assert passes == sorted(load_config("assumptions")["flood_extents"]["passes_m"])
    areas = [shape(feat["geometry"]).area for feat in g["features"]]
    assert all(a <= b * 1.01 for a, b in zip(areas, areas[1:]))   # 1% slack for simplification


def test_export_loss_counts_match_assets_and_top3():
    """Decision 2026-10-08: has_coastal_loss per asset and scenario; the portfolio count ("17 of 129") equals the
    number of assets flagged; the top three (129, 128, 41 in SSP2-4.5 2050) all carry loss."""
    fa, fp = OUT / "assets.geojson", OUT / "portfolio.json"
    if not (fa.exists() and fp.exists()):
        pytest.skip()
    a = json.loads(fa.read_text())["features"]
    port = json.loads(fp.read_text())
    for s, d in port["scenarios"].items():
        flagged = [f["properties"]["valuation_no"] for f in a if f["properties"]["scenarios"][s]["has_coastal_loss"]]
        assert len(flagged) == d["n_assets_with_coastal_loss"], s
        assert set(d["top3_valuation_nos"]) <= set(flagged), s
        for f in a:     # loss implies water reaches the asset within 200 years
            sc = f["properties"]["scenarios"][s]
            assert not sc["has_coastal_loss"] or sc["rp"] is not None, (s, f["properties"]["valuation_no"])
    assert port["scenarios"]["ssp245_2050"]["top3_valuation_nos"] == [129, 128, 41]
    assert port["scenarios"]["ssp245_2050"]["n_assets_with_coastal_loss"] == 17


def test_export_terrain_tiles_contract():
    """Decision 2026-10-08: terrain/{z}/{x}/{y}.png only, configured zooms, 256 px terrarium RGB with plausible
    Hong Kong heights; attribution carried in meta.json."""
    d = OUT / ex.TERRAIN_DIR
    if not d.exists():
        pytest.skip()
    from PIL import Image
    from pipeline.config import load_config
    from pipeline.terrain_tiles import terrarium_decode
    tt = load_config("assumptions")["terrain_tiles"]
    files = [p for p in d.rglob("*") if p.is_file()]
    zooms = set()
    for p in files:
        z, x, y = p.relative_to(d).parts
        assert z.isdigit() and x.isdigit() and y.endswith(".png") and y[:-4].isdigit(), p
        zooms.add(int(z))
    assert zooms == set(range(tt["zooms"][0], tt["zooms"][1] + 1))
    for p in files[:: max(1, len(files) // 20)]:
        im = Image.open(p)
        assert im.size == (256, 256) and im.mode == "RGB"
        e = terrarium_decode(np.asarray(im))
        assert e.min() >= 0 and e.max() < 1000, p      # negatives set to 0; Tai Mo Shan 957 m
    meta = json.loads((OUT / "meta.json").read_text())
    assert meta["terrain"]["attribution"] == tt["attribution"] and meta["terrain"]["n_tiles"] == len(files)


def test_key_paths_and_level_keys():
    obj = {"assets": [{"margin_cm": 9, "x": {"lowest_floor_mpd": 3.8}}], "observed_peak_mcd": 3.88}
    assert ex.key_paths(obj, ex.MARGIN_KEYS) == ["/assets[0]/margin_cm"]
    assert ex.level_keys(obj) == ["/assets[0]/x/lowest_floor_mpd"]


def test_export_margins_exception_only_two_named_assets():
    """Level rule (decision 2026-10-12): "Absolute ground, entrance, floor or sill levels are never published as numbers.
    Results are published as return periods with their ±0.15 m range, which bound those levels; this is accepted because
    the levels derive from open CEDD LiDAR and the published form carries its uncertainty. Relative margins in cm are
    published only for The Quayside and Chai Wan Car Service Centre." Checked here: margins only for 126 (2050
    margins) and 129 (Mangkhut replay); no file carries an absolute mPD / mCD key other than the cited HKO gauge peak."""
    from pipeline.config import load_config
    se = load_config("assumptions")["site_export"]
    assert set(se["margin_assets"]) <= ex.MARGIN_EXCEPTION["assets"]
    assert {e["valuation_no"] for e in se["event_assets"]} <= ex.MARGIN_EXCEPTION["events"]
    files = [f for f in _files() if f.is_file()]
    for f in files:
        obj = json.loads(f.read_text())
        assert not ex.level_keys(obj), f"{f.name}: {ex.level_keys(obj)}"
        if f.name != "margins.json":
            assert not ex.key_paths(obj, ex.MARGIN_KEYS), f"{f.name}: {ex.key_paths(obj, ex.MARGIN_KEYS)}"
    m = json.loads((OUT / "margins.json").read_text())
    assert {a["valuation_no"] for a in m["assets"]} <= ex.MARGIN_EXCEPTION["assets"]
    assert {e["valuation_no"] for e in m["events"]} <= ex.MARGIN_EXCEPTION["events"]
    for a in m["assets"]:
        assert set(a) == {"valuation_no", "name", "onset_basis", "value_rank_hk", "valued_above", "margins_cm", "reached"}
    for e in m["events"]:
        assert set(e) == {"valuation_no", "name", "event", "gauge_name", "observed_peak_mcd", "peak_source",
                          "above_entry_cm", "below_floor_cm", "flooded"}


def test_display_name():
    assert ex.display_name("Car Park within Wang Fuk Court*") == "Car Park within Wang Fuk Court"
    assert ex.display_name("Off Anderson Road Development Site\n(SD3 Lot 1078)") == "Off Anderson Road Development Site (SD3 Lot 1078)"


def test_export_names_have_no_footnote_marks():
    a = json.loads((OUT / "assets.geojson").read_text()) if (OUT / "assets.geojson").exists() else pytest.skip()
    for f in a["features"]:
        n = f["properties"]["name"]
        assert n == ex.display_name(n), n
