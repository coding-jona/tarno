# `tarno_backend/utils/` — small shared helpers

Cross-cutting helpers with no home in a more specific subpackage. Kept
deliberately small — anything that grows a real domain (logging config,
security) gets its own subpackage instead (`telemetry/`, `security/`).

## Files

- **`paths.py`**: the centralized, move-resistant repo-path resolver —
  `find_repo_root()` walks up from the current file looking for a directory
  that has both a `.git` folder and a `src/` folder, then exposes
  `REPO_ROOT`, `SRC_DIR`, `CONFIG_DIR`, `WORKSPACE_DIR`, `DEBUG_DIR`,
  `DOCS_DIR` as ready-to-use constants. Added specifically to stop
  hand-counting `Path(__file__).parent.parent...` hops, which breaks
  silently every time a folder moves.
  ⚠️ **Not usable inside a PyInstaller bundle** — a frozen `.exe` has no
  `.git` or `src/` marker on disk (`sys._MEIPASS` instead). Code that must
  also run bundled (`core/ovos_engine.py`'s `_BUNDLE_ROOT`,
  `ui/winui_launcher.py`'s `_project_root()`) intentionally keeps manual
  relative hop-counting instead of importing this module, with an inline
  comment explaining why at each such site.
- **`log.py`**: thin facade — `setup_logging()` delegates to
  `tarno_backend/telemetry/logging.py`'s `configure_logging()`. Exists so
  call sites don't need to know the telemetry module's internal API.
- **`text.py`**: small text helpers shared across the backend (e.g. string
  normalization used by voice/NLU code).

## Cross-references

- Actual logging setup: `tarno_backend/telemetry/logging.py` (see
  `telemetry_README.md`)
- The two deliberate exceptions to `paths.py` usage: `tarno_backend/core/ovos_engine.py`
  and `tarno_backend/ui/winui_launcher.py` (see `core_README.md`, `ui_README.md`)
