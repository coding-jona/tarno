"""Central, move-resistant filesystem path resolution.

Every place in this codebase that needed "the repo root" or "the config
directory" used to compute it by counting `Path(__file__).resolve().parent`
hops by hand. That number silently goes stale every time a file moves to a
different depth (this bit us repeatedly during the 2026-08 workspace
restructure: config.py, ovos_engine.py, winui_launcher.py, pages.py, several
tests and debug tools all needed re-counting after tarno/ -> src/tarno_backend/
and tests/ -> workspace/debug/tests/).

Fix: resolve the repo root once, here, by walking up from this file until a
directory containing both `.git` and `src` is found - robust to any future
directory-depth change, no hop-counting anywhere else in the codebase.
"""
from __future__ import annotations

import sys
from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from `start` (default: this file's location) to the repo root.

    In a PyInstaller frozen bundle, returns the directory containing the executable.
    Otherwise, the repo root is identified as the first ancestor directory that
    contains both a `.git` entry and a `src` directory.
    """
    # 1. Wenn die App als PyInstaller-Bundle läuft:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent

    # 2. Entwicklungsumgebung (normaler Python-Lauf):
    current = (start or Path(__file__)).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists() and (candidate / "src").is_dir():
            return candidate
    raise RuntimeError(
        "Could not locate the repo root (no ancestor of "
        f"'{current}' has both a .git entry and a src/ directory)"
    )


REPO_ROOT = find_repo_root()
SRC_DIR = REPO_ROOT if getattr(sys, "frozen", False) else REPO_ROOT / "src"
CONFIG_DIR = REPO_ROOT / "config"
WORKSPACE_DIR = REPO_ROOT / "workspace"
DEBUG_DIR = WORKSPACE_DIR / "debug"
DOCS_DIR = DEBUG_DIR / "docs"