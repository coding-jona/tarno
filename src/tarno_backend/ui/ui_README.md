# `tarno_backend/ui/` — ⚠️ DEPRECATED PySide6 control UI

> **Do not build new features here.** The primary, actively developed
> frontend is `src/TARNO.UI/` (C#/WinUI 3). This package is kept only as
> the `--legacy-ui` fallback (TD-017) and is explicitly marked deprecated
> in its own `__init__.py` docstring: *"PySide6-Legacy-Steuer-UI (deprecated)"*.

## Why it still exists

`tarno_backend/core/service_mediator.py` and a few other core modules still
import `PySide6` unconditionally (not behind a feature flag), so this
package can't be deleted outright without first untangling those imports.
See TD-006 in the tech-debt catalog for the full history — both UI stacks
(`tarno_backend/ui/`, `tarno_backend/gui/`, and the WinUI frontend) were maintained in
parallel for a while; only the deprecation *notice* was added so far, the
code itself is unchanged.

## Files (for reference only)

- `control_app.py` / `control_window.py`: main control application/window.
- `app.py`: PySide6 GUI entry point.
- `overlay_window.py`: transparent desktop status overlay.
- `tray.py`: system tray icon.
- `settings_dialog.py` / `confirmation_dialog.py`: settings + risky-action
  confirmation dialogs (superseded by WinUI's `SettingsPage` /
  `PermissionDialog`).
- `bus_listener.py` / `engine_controller.py`: OVOS-bus wiring, runs the
  OVOS engine in a `QThread`.
- `console.py`: console-only interface (no Qt).
- `theme.py`: dark Qt theme.
- `winui_launcher.py`: **not deprecated** — this one launches the WinUI
  3 frontend + gRPC backend and is the actual production launch path,
  it just happens to live in this folder historically.

## Cross-references

- Current frontend: `src/TARNO.UI/`
- Deprecation decision: [`workspace/debug/docs/technical-debt-catalog.md`](../../../workspace/debug/docs/technical-debt-catalog.md) TD-006, TD-017
