"""Public-repo support (decision 2026-10-12). The public tree has no scripts/, no Link inputs and no transcribed
config (config/local/), so some tests cannot run there:
- test modules that load a script from scripts/ at import time are not collected;
- a test that fails only because a private input file is missing (scripts/, config/local/, data/interim/,
  data/processed/, data/raw/, data/manual_local/) is reported as skipped, with the missing path's folder.
Neither applies in the working repo (config/local/ exists there, tracked .gitkeep), where every test runs as before."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_TREE = not (ROOT / "config" / "local").is_dir()
PRIVATE_DIRS = [ROOT / "scripts", ROOT / "config" / "local", ROOT / "data" / "interim", ROOT / "data" / "processed",
                ROOT / "data" / "raw", ROOT / "data" / "manual_local"]

collect_ignore = []
if PUBLIC_TREE and not (ROOT / "scripts").is_dir():
    for p in sorted(Path(__file__).parent.glob("test_*.py")):
        text = p.read_text()
        if re.search(r'^_spec = .*ROOT / "scripts"', text, re.M) or text.startswith('"""Tests for scripts/'):
            collect_ignore.append(p.name)


def _private_missing(exc: BaseException) -> Path | None:
    """The missing private folder behind an error: FileNotFoundError on a path in it, or any error (e.g. a GDAL / pyogrio
    data-source error) whose message names a path in a private folder that does not exist in this tree."""
    name = getattr(exc, "filename", None)
    if isinstance(exc, FileNotFoundError) and name:
        path = Path(name).resolve()
        return next((d for d in PRIVATE_DIRS if path == d or d in path.parents), None)
    msg = str(exc)
    return next((d for d in PRIVATE_DIRS if str(d) + "/" in msg and not d.is_dir()), None)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    outcome = yield
    if not PUBLIC_TREE or outcome.excinfo is None:
        return
    d = _private_missing(outcome.excinfo[1])
    if d is not None:
        outcome.force_exception(pytest.skip.Exception(
            f"needs private input ({d.relative_to(ROOT)}/), not in the public repo", _use_item_location=True))
