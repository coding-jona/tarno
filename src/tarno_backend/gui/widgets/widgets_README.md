# `tarno_backend/gui/widgets/` — legacy BuildMC-styled GUI widgets

⚠️ Part of the deprecated `gui/` stack — see [`gui_README.md`](../gui_README.md)
(TD-006) for why and what replaces it (`src/TARNO.UI/`).

## Files

- **`chat_panel.py`**: chat panel — BuildMC AI `Chat.tsx` clone for TARNO.
- **`sidebar.py`**: BuildMC-style navigation sidebar with icon+label items.
- **`mic_indicator.py`**: microphone toggle button with state indicator.
- **`status_bar.py`**: bottom status bar showing provider and state.

Note: `tarno_backend/ui/widgets/status_bar.py` is a *different* file with
the same name in the *other* deprecated UI stack (`ui/`) — not a
duplicate/mistake, just two independent legacy stacks that happened to name
a file the same way.

## Cross-references

- Parent package / deprecation context: [`gui_README.md`](../gui_README.md)
- Active replacement: `src/TARNO.UI/`
