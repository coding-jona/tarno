# `tarno_backend/config/` — reserved namespace, currently empty

⚠️ **Naming trap:** this is *not* where TARNO's runtime configuration lives.
It is an empty Python subpackage (only `__init__.py`, no content), reserved
as a namespace for future config-loading code that needs to live inside the
importable package (e.g. schema/validation helpers).

The actual configuration **files** (persona JSON, YAML config, etc.) live at
the repo-root `config/` directory, resolved via `CONFIG_DIR` in
[`tarno_backend/utils/paths.py`](../utils/utils_README.md) — a completely
different folder from this one, despite the identical name. Config
*loading* logic (reading/writing those files) currently lives in
`tarno_backend/core/config.py` (see `core_README.md`), not here.

If this package stays empty going forward, consider removing it rather than
keeping a same-named-but-different folder around as a source of confusion.

## Cross-references

- Actual config directory: `CONFIG_DIR` in [`utils/paths.py`](../utils/utils_README.md)
- Config load/save logic: `tarno_backend/core/config.py` (see [`core_README.md`](../core/core_README.md))
