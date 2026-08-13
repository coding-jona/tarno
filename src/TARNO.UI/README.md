# TARNO.UI — WinUI 3 frontend

The active, production Windows frontend for TARNO (C#/WinUI 3). Talks to the
Python backend (`src/tarno_backend/`) exclusively over gRPC — see
[`grpc_README.md`](../tarno_backend/grpc/grpc_README.md) for the wire
protocol and `GrpcClientService.cs` below for the client side.

This is the only actively developed UI. The two Python-based UI stacks
under `src/tarno_backend/` (`ui/`, `gui/`) are legacy/deprecated — see
[`ui_README.md`](../tarno_backend/ui/ui_README.md) and
[`gui_README.md`](../tarno_backend/gui/gui_README.md) (TD-006).

## Layout

- **`Pages/`**: one page per app section (`ChatPage`, `VoicePage`,
  `CodeWorkspacePage`, `MemoryPage`, `TasksPage`, `WorkspacesPage`,
  `SettingsPage`, `ApiKeysPage`, `LogsPage`, `HomePage`,
  `MeshDashboardPage`/`MeshDevicesPage` for the Dynamic-Hybrid-Mesh
  feature — see `tarno_backend/integrations/integrations_README.md`).
- **`Services/`**: application services — `GrpcClientService.cs` (backend
  connection with auto-reconnect, TD-003), `PermissionService.cs`
  (confirmation dialogs for risky backend actions, TD-025),
  `ProviderOnboardingService.cs` (API-key onboarding, ADR-006), plus
  per-feature stores (`ChatStore`, `SettingsStore`, `WorkspaceStore`,
  `LayoutStore`, `SidebarStateStore`, `CodeLayoutPresetStore`,
  `MeshCredentialStore`) and drag/docking/pegboard services for the
  panel layout system (ADR-005). The `AprilFools*.cs` services are a
  seasonal easter egg, not core functionality.
- **`ViewModels/`**: MVVM view models backing the pages/panels.
- **`Models/`**: plain data models and interfaces (`IDraggablePanel`,
  `IPegboardPanel`, layout models).
- **`Controls/`**, **`UserControls/`**: custom WinUI controls and composed
  UI building blocks.
- **`Converters/`**: XAML value converters.
- **`Dialogs/`**: modal dialogs (e.g. `ChatSettingsDialog`).
- **`Windows/`**: secondary window definitions (multi-window/multi-monitor
  support, ADR-005).
- **`Composition/`**, **`Styles/`**, **`DesignTokens/`**: visual layer —
  Composition API effects, XAML styles, and design tokens (colors,
  spacing) that back them. See TD-011 for known design-system
  inconsistencies (old token names still present in some pages).
- **`Strings/`**: localized/UI-facing strings (German persona/UI text per
  `CLAUDE.md`'s "UI strings and logs in German" rule).
- **`Helpers/`**: small static helper utilities.
- **`Assets/`**: images/icons bundled with the app.

Note: `cmd_out.txt`, `cmd_err.txt`, `xamlout.txt`, `xamlerr.txt`,
`xc_out.txt`, `xc_err.txt`, `xc17_out.txt` may appear here locally as build
scratch output — they're git-ignored, not part of the source.

## Build

```
dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64
```

## Cross-references

- Backend it talks to: [`tarno_backend/core/core_README.md`](../tarno_backend/core/core_README.md)
- gRPC contract: [`tarno_backend/grpc/grpc_README.md`](../tarno_backend/grpc/grpc_README.md)
- Architecture decisions: [`workspace/debug/docs/adr/`](../../workspace/debug/docs/adr/)
  (ADR-001: UI framework choice, ADR-005: Pegboard/multi-monitor,
  ADR-006: provider onboarding)
- Known issues: [`workspace/debug/docs/technical-debt-catalog.md`](../../workspace/debug/docs/technical-debt-catalog.md)
  (TD-003, TD-011, TD-025)
