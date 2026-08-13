# `tarno_backend/first_start/` — first-run setup wizard

Guides a new user through initial setup: hardware detection, audio/wake-word
choice, privacy settings, LLM provider selection, and model downloads. Built
with PySide6, the same legacy UI stack flagged as deprecated in
[`ui_README.md`](../ui/ui_README.md) (TD-006) — the wizard has **not** yet
been ported to WinUI (see TD-017 in the tech-debt catalog, marked resolved
for the *main* UI but this wizard predates that fix and should be checked).

## Files

- **`wizard.py`**: the `QWizard` shell that sequences the pages below.
- **`pages.py`**: the individual wizard pages (welcome, hardware, audio,
  wake-word, privacy, provider, model download).
- **`hardware_detection.py`**: lightweight hardware and audio device
  detection used by `HardwarePage`.
- **`config_initializer.py`**: writes the user configuration collected across
  the wizard pages to disk once the user finishes.

## Cross-references

- Docs link opened from `ProviderPage._open_help()`: `DOCS_DIR / "api-keys.md"`
  via [`utils/paths.py`](../utils/utils_README.md) — dev-only path, not valid
  inside a PyInstaller bundle.
- Config actually written: `tarno_backend/core/config.py` (see `core_README.md`)
- Deprecated-UI-stack context: [`ui_README.md`](../ui/ui_README.md), TD-006, TD-017
  in [`workspace/debug/docs/technical-debt-catalog.md`](../../../workspace/debug/docs/technical-debt-catalog.md)
