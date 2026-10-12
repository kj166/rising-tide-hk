"""Load config/*.yaml with the gitignored config/local/*.yaml overlay.

Tracked config holds every key, its `# source:` comment and page refs. Values
transcribed from third-party documents (PWDM, HKO) live only in config/local/<name>.yaml,
which is laid over the tracked file on load. The overlay may only fill keys that
already exist in the tracked file, so the tracked file stays the full list of inputs.
"""

from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def overlay(base: dict, local: dict, path: str = "") -> dict:
    """Return a copy of `base` with values from `local` laid over it, recursively.

    Raises KeyError for a key in `local` that is not in `base`, and TypeError where
    one side is a mapping and the other is not.
    """
    merged = dict(base)
    for key, value in local.items():
        where = f"{path}.{key}" if path else str(key)
        if key not in base:
            raise KeyError(f"config/local key not in tracked config: {where}")
        if isinstance(base[key], dict) or isinstance(value, dict):
            if not (isinstance(base[key], dict) and isinstance(value, dict)):
                raise TypeError(f"config/local shape differs from tracked config at {where}")
            merged[key] = overlay(base[key], value, where)
        else:
            merged[key] = value
    return merged


def load_config(name: str, config_dir: Path = CONFIG_DIR) -> dict[str, Any]:
    """Load config/<name>.yaml, overlaid with config/local/<name>.yaml if present."""
    base = yaml.safe_load((config_dir / f"{name}.yaml").read_text()) or {}
    local_path = config_dir / "local" / f"{name}.yaml"
    if not local_path.exists():
        return base
    local = yaml.safe_load(local_path.read_text()) or {}
    return overlay(base, local)
