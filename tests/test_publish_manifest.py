"""Publication check (decision 2026-10-08): no file listed under "Public" in docs/PUBLISH_MANIFEST.md may contain an
mPD water or sill level next to a named asset. Per-asset levels are outside the export contract; the site shows only
cm margins (margins.json)."""

import fnmatch
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEVEL = re.compile(r"\b\d+(?:\.\d+)?\s*m(?:PD|CD)\b")
ASSET_REF = re.compile(r"\bnos?\.\s*\d+", re.I)
BINARY = {".png", ".jpg", ".jpeg", ".webp", ".gpkg", ".parquet", ".zip", ".tif", ".pdf", ".ico", ".woff2"}


def public_patterns() -> list[str]:
    text = (ROOT / "docs" / "PUBLISH_MANIFEST.md").read_text()
    section = text.split("## Public", 1)[1].split("\n## ", 1)[0]
    pats = []
    for line in section.splitlines():
        if line.startswith("|") and not line.startswith("|---") and not line.startswith("| path"):
            pats += re.findall(r"`([^`]+)`", line.split("|")[1])
    return pats


def public_files() -> list[Path]:
    r = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode == 0:
        tracked = r.stdout.split("\n")
    else:   # an uncommitted public tree (make public stopped at a gate): every file there is a public file
        skip = {".venv", "node_modules", "build", ".svelte-kit", "test-results", "__pycache__"}
        tracked = [str(f.relative_to(ROOT)) for f in ROOT.rglob("*") if f.is_file() and not skip & set(f.parts)]
    out = set()
    for pat in public_patterns():
        for alt in pat.split("|"):                      # "site/public/data/*.json|geojson"
            alt = alt.strip()
            if not alt:
                continue
            if "." not in alt.split("/")[-1] and not alt.endswith("*") and not any(c in alt for c in "*?"):
                alt = alt.rstrip("/") + "/*"           # directory or extension-less file
            for f in tracked:
                if f and (f == pat or fnmatch.fnmatch(f, alt) or fnmatch.fnmatch(f, alt.replace("/*", "/**/*"))):
                    out.add(ROOT / f)
    return sorted(p for p in out if p.suffix.lower() not in BINARY and p.is_file())


def asset_names() -> list[str]:
    a = json.loads((ROOT / "site" / "public" / "data" / "assets.geojson").read_text())
    return [f["properties"]["name"] for f in a["features"] if len(f["properties"]["name"]) >= 6]


def level_hits(text: str, names: list[str]) -> list[str]:
    """Lines with an mPD figure and an asset reference on the same line or a neighbouring line."""
    lines = text.splitlines()
    hits = []
    for i, line in enumerate(lines):
        if not LEVEL.search(line):
            continue
        near = " ".join(lines[max(0, i - 1): i + 2])
        if ASSET_REF.search(near) or any(n in near for n in names):
            hits.append(f"{i + 1}: {line.strip()[:160]}")
    return hits


def test_level_hits_detects_named_levels():
    # synthetic names and values only (this file is public)
    names = ["Example Plaza"]
    level = "987.65 " + "mPD"
    assert level_hits(f"Example Plaza sill {level}", names)
    assert level_hits(f"no. 999: entry {level}", names)
    assert level_hits("Example Plaza peak 987.65 " + "mCD", names)
    assert not level_hits(f"0.50 mCD = {level} (datum example)", names)
    assert not level_hits("Example Plaza margin about 9 cm", names)


def test_manifest_lists_files():
    files = public_files()
    assert any(p.parts[-2:] == ("pipeline", "07_export.py") for p in files)
    assert not any("docs/internal" in str(p) for p in files)
    assert not any(p.name == "DESIGN_BRIEF.md" for p in files)      # conditional until section 9 is removed


def test_public_files_have_no_named_asset_levels():
    names = asset_names()
    bad = {}
    for p in public_files():
        try:
            h = level_hits(p.read_text(errors="ignore"), names)
        except UnicodeDecodeError:
            continue
        if h:
            bad[str(p.relative_to(ROOT))] = h
    assert not bad, bad
