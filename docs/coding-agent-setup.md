# TARNO Coding Agent — Kurzanleitung

## Was ist der Coding-Agent?

Der Coding-Agent ist ein separater Modus in TARNO, der über die Seitenleiste mit **Chat** ↔ **Code** umgeschaltet wird. Im Code-Modus arbeitet TARNO in definierten Workspaces, liest und schreibt Dateien und führt Befehle in einem integrierten Terminal aus.

## Workspaces einrichten

1. Seitenleiste auf **Code** stellen.
2. **Workspaces verwalten** öffnen.
3. Mit **Hinzufügen** einen neuen Workspace anlegen.
4. Den Projektordner über **Durchsuchen** wählen.
5. Include-/Exclude-Patterns anpassen (z.B. `src/**`, `.env`, `bin/`).
6. **Speichern** klicken.

Workspaces werden in `%LOCALAPPDATA%\TARNO\workspaces.json` gespeichert.

## Aktion-Modus

Im Chat-Header kann zwischen drei Modi gewechselt werden:

- **Plan** — Aktionen werden nur vorgeschlagen, nicht ausgeführt.
- **Manual** — TARNO fragt vor Dateizugriffen und Befehlen.
- **Auto** — Erlaubte Aktionen innerhalb des Workspaces werden sofort ausgeführt.

## Terminal nutzen

- Im Chat-Modus auf das **🖥** Symbol in der Eingabezeile klicken.
- Befehle eingeben und mit Enter absenden.
- Das Terminal arbeitet im Working-Directory des aktiven Workspaces.

## Live ThoughtStream

- Über das **🧠** Symbol in der Eingabezeile das ThoughtStream-Panel ein-/ausblenden.
- Zeigt in Echtzeit:
  - Gedankengänge (Chain-of-Thought) als einklappbare Blöcke
  - Lese-/Schreibzugriffe auf Dateien
  - Ausgeführte Shell-Befehle mit Status
  - Neue/veränderte Dateien mit Inline-Code-Snippet
- Die Daten kommen per gRPC-Stream vom Backend (`AgentTrace` Events).

## Sicherheit

- Dateizugriffe sind auf den Workspace-Root beschränkt.
- Exclude-Patterns schützen sensible Dateien wie `.env` oder `*.secret`.
- Schreiboperationen nutzen atomisches Schreiben mit Backup (`.bak`).

## Provider-Modelle

Im Provider-Flyout stehen Mistral-Coding-Modelle zur Verfügung, z.B. `codestral-2508`. Diese sind für Code-Optimierung und längere Kontexte geeignet.

## Verzeichnis der neuen Dateien

- `src/TARNO.UI/Models/Workspace.cs`
- `src/TARNO.UI/Models/CodingAction.cs`
- `src/TARNO.UI/Models/ActionMode.cs`
- `src/TARNO.UI/Services/WorkspaceStore.cs`
- `src/TARNO.UI/Services/FileAccessService.cs`
- `src/TARNO.UI/Services/TerminalService.cs`
- `src/TARNO.UI/Services/PermissionService.cs`
- `src/TARNO.UI/Pages/WorkspacesPage.xaml` / `.cs`
- `src/TARNO.UI/Pages/ChatPage.xaml` / `.cs` (erweitert)
- `src/TARNO.UI/MainWindow.xaml` / `.cs` (erweitert)
- `src/TARNO.UI/ViewModels/MainViewModel.cs` (erweitert)
- `tarno/ai/model_catalog.py` (erweitert)
- `docs/coding-agent-setup.md`
