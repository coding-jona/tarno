# `tarno_backend/gui/` — ⚠️ DEPRECATED PySide6 "BuildMC" GUI

> **Do not build new features here.** Its own `__init__.py` docstring
> says it outright: *"PySide6 BuildMC-Clone-GUI (deprecated, eingefroren)"*
> — frozen, not maintained. The active frontend is `src/TARNO.UI/`
> (C#/WinUI 3). See `tarno_backend/ui/ui_README.md` for the *other* deprecated
> legacy GUI and why both still exist (TD-006).

## What it was

A clone of a "BuildMC AI" desktop layout (`main_window.py`'s docstring:
*"Main application window — BuildMC AI Layout.tsx clone"*), built before
the WinUI 3 frontend was settled on.

## Files (for reference only)

- `main_window.py`: the main window.
- `theme.py`: the BuildMC-clone theme.
- `log_bridge.py`: bridges Python `logging` records onto the Qt main
  thread so log messages can be displayed in the GUI.
- `pages/`, `widgets/`: page/widget subpackages for this GUI.

## Cross-references

- Current frontend: `src/TARNO.UI/`
- Deprecation decision: [`workspace/debug/docs/technical-debt-catalog.md`](../../../workspace/debug/docs/technical-debt-catalog.md) TD-006
