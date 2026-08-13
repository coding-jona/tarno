# ADR-004: Pegboard- und Multi-Monitor-UI

**Status:** Entschieden / Umgesetzt

**Entscheidungshalter:** TARNO UI Team

**Betroffene Komponenten:** WinUI 3 Frontend (`TARNO.UI`)

---

## Kontext

TARNO benötigt eine flexible UI, die auf mehreren Monitoren arbeitet und vom Nutzer frei angeordnet werden kann. Bisherige Panels waren an feste Raster-Grids gebunden und nutzten OS-Drag-and-Drop für das Verschieben in schwebende Fenster. Das führte zu Layoutverlust, fehlender Snap-Positionierung und inkonsistentem Zustand zwischen Haupt- und Pop-Out-Fenstern.

## Entscheidung

1. **`SnapCanvas` als zentrales Lochbrett-Panel**
   - Ein benutzerdefiniertes `Canvas`, das Children an einer virtuellen Gitterzelle ausrichtet.
   - Position und Größe werden über Attached Properties (`GridX`, `GridY`, `GridColumns`, `GridRows`, `Scale`) festgelegt.
   - `GridSize` ist konfigurierbar (8–48 px, Standard 24 px).

2. **`IPegboardPanel` und `DraggableSection` für alle Panels**
   - `DraggableSection` implementiert `IPegboardPanel` und liefert Header, Resize-Griff und Pop-Out-Button.
   - Drag, Resize und Pop-Out erfolgen ausschließlich per Pointer-Events innerhalb des `SnapCanvas`, nicht über das OS-Drag-Drop-System.

3. **Multi-Monitor Pop-Out via `PegboardService` und `PanelWindow`**
   - Klick auf das Pop-Out-Icon entfernt das Panel aus dem `SnapCanvas` und hostet es in einem neuen `PanelWindow` auf dem nächsten verfügbaren Monitor.
   - `PanelWindow` erhält das zentrale `MainViewModel` als `DataContext`; so bleibt das Single-Brain-Prinzip erhalten.

4. **Layout-Persistenz in `LayoutStore` / `PegboardService`**
   - Jede Drag-, Resize- und Pop-Out-Operation speichert Position, Größe und Fenster-Index nach `%LOCALAPPDATA%\TARNO\layout.json`.
   - Beim Seitenwechsel (`OnNavigatedTo`) wird `PegboardService.RestoreLayout` aufgerufen.

5. **Cross-Window Sync via `WindowMessageBus`**
   - `WeakReferenceMessenger` wird in einer statischen `WindowMessageBus`-Klasse gekapselt.
   - `MainViewModel` published UI-relevante Ereignisse (`ProviderChangedMessage`, `ChatMessageReceivedMessage`, ...), die in Pop-Out-Fenstern subscribiert werden können.

6. **Fokus- und Z-Index-Management**
   - Beim Starten eines Drag wird das betroffene Panel in den Vordergrund gebracht (`Canvas.SetZIndex`) und erhält den Fokus.

## Konsequenzen

- **Positiv:** Konsistentes Multi-Monitor-Verhalten, wiederverwendbare Lochbrett-Logik, Single-Brain-Architektur bleibt, Layout über Sitzungen hinweg stabil.
- **Negativ:** Starke Kopplung an `SnapCanvas` und `PegboardService`; Nicht-`IPegboardPanel`-Controls (z. B. `CodingPanelControl`, `TerminalPanelControl`) werden zunächst nur angeordnet, müssen aber noch vollständig in das Pegboard-Verhalten migriert werden.
- **Risiko:** Bei sehr großen `SnapGridSize`-Werten (> 48) oder winzigen Grids (< 8) kann das Layout überlappen oder zu klein wirken. Der Slider in den Einstellungen begrenzt den Bereich.

## Verifizierung

- `dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64` ist grün (0 Fehler).
- `HomePage`, `ChatPage` und `CodeWorkspacePage` verwenden jeweils einen `SnapCanvas`.
- Einstellungen (`PegboardEnabled`, `SnapGridSize`) sind an `SettingsViewModel` und die Canvas-Elemente gebunden.
