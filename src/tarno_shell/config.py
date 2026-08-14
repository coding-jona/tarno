"""Configuration loader for tarno_shell (YAML based)."""
import os
from pathlib import Path

try:
    import yaml
except Exception:
    yaml = None


def load_config(path: str | None) -> dict:
    if path is None:
        return {}
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    if yaml is None:
        raise RuntimeError("PyYAML is required to load YAML configs. Install with: pip install pyyaml")
    with p.open('r', encoding='utf-8') as fh:
        return yaml.safe_load(fh) or {}
