# Block 8: Adaptive UI-Canvas, Multi-Monitor Pop-Out & Fensterübergreifende Zustandssynchronisation

> Erweiterung des `tarno-70-phase-masterplan.md`. Dieser Block baut direkt auf **Phase 38 (universelles Drag-and-Dock)** und den bereits existierenden Services `DockingService`, `PanelWindow`, `MultiScreenLayoutService` und `WindowStateCoordinator` auf.

## Ziel

Alle UI-Elemente (Chat, Agenten-Logs, File Explorer, Terminals, Coding, Context) verhalten sich im Hauptfenster wie Werkzeuge an einer Lochwand:

- Frei mit der Maus verschiebbar.
- Skalier- und größenveränderbar.
- An unsichtbaren Rasterpunkten ausrichtbar (Snap-to-Grid).
- Kein neues Betriebssystem-Fenster entsteht, nur weil man innerhalb des Hauptfensters zieht.

Multi-Monitor-Pop-Out passiert **nur explizit** über ein Icon im Panel-Header. Ausgelagerte Fenster teilen sich den Zustand mit dem Hauptfenster in Echtzeit, ohne doppelte Backend-Aufrufe.

## Technologie-Mapping: User-Vorschlag → TARNO/WinUI 3

| User-Idee | Realität in TARNO (WinUI 3) | Begründung |
|---|---|---|
| **Gridstack.js / Dockview** | Custom `SnapCanvas` (`Canvas`-basiertes Custom Control) | WinUI 3 ist keine Browser-Runtime. Externe Web-Libraries würden einen `WebView2`-Host benötigen, der deutlich schwerer und schlechter integrierbar ist. Ein natives Custom Control hat volle `Manipulation`-, `Pointer`- und `Dispatcher`-Kontrolle. |
| **window.open() Pop-Out** | `PanelWindow` + `AppWindow` / `DisplayArea` | Bereits vorhanden. `PanelWindow` ist das native WinUI-Äquivalent eines schlanken Pop-Outs. `MultiScreenLayoutService` kümmert sich um den richtigen Monitor. |
| **BroadcastChannel / SharedWorker** | In-Process `WindowMessageBus` (statischer Publisher/Subscriber oder `WeakReferenceMessenger`) | BroadcastChannel gibt es in WinUI 3 nicht. Da alle Fenster im selben Prozess laufen, reicht ein in-memory Bus. `SharedWorker` wäre Web-Technologie und ohne Mehrwert. |
| **Hauptfenster = "Gehirn"** | `MainWindow` hält den einzigen `GrpcClientService` + das einzige `MainViewModel`. Pop-Outs bekommen nur einen Read-Only-View auf dieselbe ViewModel-Instanz. | Verhindert doppelte gRPC-Streams, Race Conditions und überflüssige KI-Aufrufe. |

**Hard Constraint:** Keine neuen Runtime-Dependencies ohne separate Freigabe. Alles baut auf WinUI 3 SDK, `CommunityToolkit.Mvvm` und dem bestehenden TARNO-Stack auf.

## Architektur-Entscheidungen

1. **In-Fenster-Drag** benutzt `PointerPressed`/`PointerMoved`/`PointerReleased` (bzw. `Manipulation`-Events) auf dem Panel-Header, **nicht** den OS-Drag-Drop-Pfad. Dadurch bleibt die Drag-Vorschau im Hauptfenster und es öffnet sich kein OS-Fenster.
2. **Cross-Window-Drag** (zurück aus einem Pop-Out ins Hauptfenster) nutzt weiterhin `CanDrag`/`Drop`, weil hier eine Fenstergrenze überschritten werden muss.
3. Jedes Panel implementiert `IDraggablePanel` (bestehend) und optional das neue `IPegboardPanel` mit Grid-Zelle, Spannen und Skalierung.
4. **Ein Panel kann nur an einem Ort leben:** Entweder in der `SnapCanvas` des Hauptfensters oder in einem `PanelWindow`. Ein Wechsel entfernt das Element aus der alten Parent-Visual und setzt es in die neue.
5. **Zustandssynchronisation** geschieht primär über das gemeinsame `MainViewModel` (gleiche Instanz in allen Fenstern) plus `WindowMessageBus` für granularere Events, die nicht über `INotifyPropertyChanged` abbildbar sind.

## Betroffene Hauptkomponenten

- `src/TARNO.UI/Controls/SnapCanvas.cs` (neu)
- `src/TARNO.UI/Controls/PegboardPanel.cs` (neu, Custom Control)
- `src/TARNO.UI/Services/PegboardService.cs` (neu)
- `src/TARNO.UI/Services/WindowMessageBus.cs` (neu)
- `src/TARNO.UI/Services/DockingService.cs` (erweitern)
- `src/TARNO.UI/Services/MultiScreenLayoutService.cs` (erweitern)
- `src/TARNO.UI/Windows/PanelWindow.xaml`/.cs (anpassen)
- `src/TARNO.UI/UserControls/DraggableSection.xaml`/.cs (Pop-Out-Icon)
- `src/TARNO.UI/UserControls/ExplorerPanelControl.xaml`/.cs
- `src/TARNO.UI/UserControls/ContextDockPanelControl.xaml`/.cs
- `src/TARNO.UI/UserControls/CodingPanelControl.xaml`/.cs
- `src/TARNO.UI/UserControls/TerminalPanelControl.xaml`/.cs
- `src/TARNO.UI/Pages/CodeWorkspacePage.xaml`/.cs
- `src/TARNO.UI/Models/IPegboardPanel.cs` (neu)
- `src/TARNO.UI/Models/PanelLayoutModel.cs` / `MultiScreenLayoutModel.cs` (erweitern)
- `src/TARNO.UI/Services/LayoutStore.cs` (erweitern)
- `src/TARNO.UI/ViewModels/MainViewModel.cs` (Pop-Out-Commands, Bus-Nachrichten)
- `config/default.yaml` + `tarno/core/config.py` (UI-Config-Erweiterungen)
- `tests/` (neue Layout- und Bus-Unit-Tests)

## Bekannte Risiken

- **UIElement-Elternproblem:** Ein `FrameworkElement` kann immer nur ein Parent haben. Pop-Out/Back-Dance muss `parent.Children.Remove()` + `newParent.Children.Add()` atomisch ausführen.
- **Threading/Dispatcher:** Mehrere `Window` teilen denselben UI-Thread, aber `XamlRoot` unterscheidet sich. Bindings funktionieren, `DispatcherQueue`-Zugriff muss aber auf dem richtigen Fenster erfolgen.
- **Fokus bei Eingaben im Pop-Out:** Text-Input im Pop-Out muss entweder ans Hauptfenster weitergereicht oder über das gemeinsame ViewModel synchronisiert werden.
- **Skalierung vs. Readability:** Zu starke Skalierung macht Text unlesbar. Min/Max-Grenzen und Per-Panel-Reset sind notwendig.

---

## Phasen

### Phase 71: SnapCanvas Proof-of-Concept

**Ziel:** Validieren, dass ein `Canvas`-basiertes Custom Control Drag + Snap in WinUI 3 sauber abbilden kann, bevor es in die echte Arbeitsfläche eingebaut wird.

**Deliverables:**
- `src/TARNO.UI/Controls/SnapCanvas.cs` (Prototyp)
- Test-Page `SnapCanvasTestPage.xaml` (später wieder entfernt)
- Snap-Grid 24px, ziehbares Rechteck, das an Grid-Punkten einrastet

**Verifikation:**
```powershell
dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64
```
Manueller Test: Rechteck im Test-Canvas verschieben, lässt es an den unsichtbaren Linien einrasten.

---

### Phase 72: SnapCanvas-Grundgerüst

**Ziel:** Produktives `SnapCanvas`-Control, das Children anhand von Attached Properties positioniert und skaliert.

**Deliverables:**
- `SnapCanvas` als öffentliches `Custom Control`, abgeleitet von `Canvas`
- Attached DPs:
  - `SnapCanvas.GridX` / `GridY` / `GridColumns` / `GridRows`
  - `SnapCanvas.Scale` / `IsSnapped`
- Properties: `GridSize`, `ShowGridDots`
- `ArrangeOverride`/`MeasureOverride` berücksichtigt Scale und Grid-Spannen

**Verifikation:**
```powershell
dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64
```
Unit-Test: `tests/test_snap_canvas_math.py` (C#-seitig: neuer MSTest-Projekt oder manuell im Code-Behind, falls kein UI-Test-Projekt existiert).

---

### Phase 73: In-Fenster-Drag mit Snap

**Ziel:** Panels lassen sich per Maus innerhalb des Hauptfensters verschieben und rasten ins Lochraster ein, **ohne** ein OS-Drag-Drop-Event auszulösen.

**Deliverables:**
- `PegboardDragService` (Pointer-Tracking)
- `DraggableSection` Header bekommt `PointerPressed/Moved/Released`
- Drag-Visual: halbtransparentes Ghost-Overlay innerhalb der `SnapCanvas`
- Snap-Berechnung auf Release: `GridX`, `GridY`, `GridColumns`, `GridRows` aktualisieren
- Kein `PanelWindow` wird geöffnet

**Verifikation:**
```powershell
dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64
```
Manueller Test: Chat-Sektion in `HomePage` oder `CodeWorkspacePage` ziehen, sie einrasten lassen, kein neues Fenster öffnet sich.

---

### Phase 74: Resize-Griffe und Skalierung

**Ziel:** Jedes Panel ist am rechten/unteren Rand und an der Ecke vergrößer- und skalierbar.

**Deliverables:**
- Resize-Thumbs im `DraggableSection` Header oder Rahmen
- `SnapCanvas` aktualisiert `GridColumns`/`GridRows` beim Resize (gerundet auf Grid)
- `RenderTransform.ScaleX/ScaleY` oder `SnapCanvas.Scale` pro Panel
- Min-/Max-Breite/Höhe (z. B. 120x80 bis 4 Grid-Zellen)
- Per-Panel-Reset-Button (100% Skalierung)

**Verifikation:**
```powershell
dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64
```
Manueller Test: Panel verkleinern, vergrößern, Text bleibt lesbar.

---

### Phase 75: Pop-Out-Icon und expliziter Multi-Monitor-Trigger

**Ziel:** Multi-Monitor-Pop-Out passiert nur, wenn der Nutzer das Icon im Header klickt. Kein automatisches Pop-Out beim Drag.

**Deliverables:**
- Header-Icon in `DraggableSection` und allen typisierten Panels (`ExplorerPanelControl`, `ContextDockPanelControl`, `CodingPanelControl`, `TerminalPanelControl`)
- `PegboardService.PopOutPanelAsync(panel, targetDisplayIndex)`
- `MainViewModel.PopOutCommand`
- Logik: Panel wird aus `SnapCanvas` entfernt, in `PanelWindow` verschoben, in der `SnapCanvas` bleibt ein Platzhalter zurück

**Verifikation:**
```powershell
dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64
```
Manueller Test: Pop-Out-Icon klicken → `PanelWindow` öffnet sich auf dem sekundären Monitor.

---

### Phase 76: Pop-Out-Fenster optimieren

**Ziel:** Das Pop-Out-Fenster ist schlank, minimalistisch und landet sinnvoll auf dem Ziel-Monitor.

**Deliverables:**
- `PanelWindow` bekommt optionale `AppWindow.TitleBar.ExtendsContentIntoTitleBar = true` oder minimale Titelleiste
- Standard-Größe 600×400 statt 800×600
- `MultiScreenLayoutService.OpenWindowOnDisplay(window, displayIndex)`
- `MultiScreenLayoutService.CenterOnDisplay` / `PlaceOnRightHalfOfDisplay`
- `PanelWindow` erhält immer das gleiche `MainViewModel`-Objekt

**Verifikation:**
```powershell
dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64
```
Manueller Test: Pop-Out öffnet sich auf dem richtigen Monitor, nicht im Weg des Hauptfensters.

---

### Phase 77: Layout-Persistenz erweitern

**Ziel:** Position, Größe, Skalierung und Monitor-Zugehörigkeit jedes Panels über App-Neustart hinaus speichern.

**Deliverables:**
- `IPegboardPanel` mit `GridX`, `GridY`, `GridColumns`, `GridRows`, `Scale`, `WindowIndex`
- `MultiScreenLayoutModel` erweitert um `PegboardPanels`
- `LayoutStore` speichert/liest `PanelLayoutModel` mit Grid- und Scale-Daten
- `DockingService.SaveLayoutSnapshot` / `RestoreLayout` berücksichtigen SnapCanvas-Layout

**Verifikation:**
```powershell
dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64
py -3.12 -m py_compile tarno/core/config.py
```
Unit-Test: Layout-Datei schreiben, neu einlesen, alle Felder erhalten.

---

### Phase 78: Drag zurück ins Hauptfenster

**Ziel:** Ein ausgelagertes Panel kann wieder in den Lochbrett-Bereich des Hauptfensters zurückgezogen werden.

**Deliverables:**
- `PanelWindow` Header bekommt `CanDrag` und `DragStarting` (Cross-Window)
- `SnapCanvas` als `AllowDrop`-Ziel
- `DockingService.DockToMain` refactored: statt `CodeWorkspacePage.DockPanel` nutzt es `PegboardService.InsertIntoSnapCanvas(panel, gridX, gridY)`
- Platzhalter in `SnapCanvas` wird durch das echte Panel ersetzt

**Verifikation:**
```powershell
dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64
```
Manueller Test: Panel aus `PanelWindow` ins Hauptfenster ziehen → es rastet im Lochraster ein.

---

### Phase 79: WindowMessageBus (Broadcast-Channel-Äquivalent)

**Ziel:** Leichtgewichtiger, prozessweiter Nachrichtenbus für Fenster-übergreifende UI-Events.

**Deliverables:**
- `src/TARNO.UI/Services/WindowMessageBus.cs`
- Nachrichtentypen:
  - `PanelStateChangedMessage`
  - `ProviderSwitchedMessage`
  - `ChatMessageReceivedMessage`
  - `TerminalOutputReceivedMessage`
- Publisher/Subscriber mit weak references
- `DispatcherQueue`-Aware Routing (Ziel-Fenster bekommt Nachricht auf seinem `Dispatcher`)

**Verifikation:**
```powershell
dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64
```
Unit-Test: Zwei Subscriber empfangen dieselbe Nachricht, Subscriber wird nach Dispose nicht mehr benachrichtigt.

---

### Phase 80: Single-Brain-Modell

**Ziel:** Klare Regel: nur das Hauptfenster spricht gRPC mit dem Python-Backend. Pop-Outs sind reine Renderer.

**Deliverables:**
- `PanelWindow` erhält `MainViewModel` read-only, erstellt keinen eigenen `GrpcClientService`
- `MainViewModel` dokumentiert als "Owner of GrpcClientService"
- gRPC-Listener-Registrierung zentralisiert in `MainWindow`
- Code-Review-Regel: Kein `new GrpcClientService` in `PanelWindow`

**Verifikation:**
```powershell
dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64
```
Code-Review / `grep`: kein neuer `GrpcClientService`-Konstruktor außerhalb `MainWindow`/`MainViewModel`.

---

### Phase 81: Live-Zustandssynchronisation für Pop-Outs

**Ziel:** Ausgelagerte Panels zeigen denselben Inhalt wie im Hauptfenster, ohne dass der Nutzer neu laden muss.

**Deliverables:**
- Pop-Out-`PanelWindow` zeigt das entfernte Panel `UIElement`; Binding zeigt auf dasselbe `MainViewModel`
- Für Events, die `INotifyPropertyChanged` nicht sauber triggern, publiziert `MainViewModel` über `WindowMessageBus`
- Beispiel-Integration:
  - Neuer Chat-Stream im `CodingPanel` → Pop-Out aktualisiert Scroll-View
  - Terminal-Output → Pop-Out Terminal-View aktualisiert sich
- `DispatcherQueue`-Check in `WindowMessageBus.Publish`

**Verifikation:**
```powershell
dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64
```
Manueller Test: Einen Prompt im Hauptfenster senden → Chat-Panel auf dem zweiten Monitor scrollt mit.

---

### Phase 82: Konfliktauflösung, Fokus und Input-Routing

**Ziel:** Verhindern, dass zwei Fenster denselben Content duplizieren oder denselben Befehl doppelt senden.

**Deliverables:**
- `PegboardService` trackt `PanelId → (WindowIndex, GridX, GridY)`; keine zwei Instanzen gleichzeitig
- Pop-Out-Input (z. B. Chat-Eingabe) wird entweder an `MainViewModel.SendUserMessageAsync` weitergeleitet oder der Eingabebereich wird im Pop-Out schreibgeschützt (UX-Entscheidung)
- Fokus-Regeln:
  - Klick auf Pop-Out-Panel aktiviert `PanelWindow`
  - Klick auf Platzhalter im Hauptfenster aktiviert Hauptfenster
- Doppelklick auf Platzhalter = "Dock back" / Pop-Out schließen und ins Lochraster zurückholen

**Verifikation:**
```powershell
dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64
```
Manueller Test: Eingabe im Pop-Out sendet genau eine Chat-Nachricht; doppelter Sende-Button feuert nicht doppelt.

---

### Phase 83: Weitere Panels pegboard-fähig machen

**Ziel:** Nicht nur `CodeWorkspacePage`-Panels, sondern auch Chat, Agenten-Logs und ggf. Dashboard-Kacheln können in das Lochbrett gezogen werden.

**Deliverables:**
- `ChatView` bzw. ein neues `ChatPanelControl` wird `IPegboardPanel` und kann in `SnapCanvas` leben
- Agenten-Log/Trace-Panel als `IPegboardPanel` verpacken
- `DashboardPage` bekommt optional einen "Pegboard-Modus"-Schalter
- `HomePage`, `ChatPage`, `SettingsPage` Sektionen können in `SnapCanvas` geparkt werden (oder werden in ein Workspace-Template gewandelt)

**Verifikation:**
```powershell
dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64
```
Manueller Test: Agenten-Log-Panel aus dem Dashboard in das Lochbrett ziehen und poppen.

---

### Phase 84: Einstellungen, Polish & Snap-Visualisierung

**Ziel:** Produktionsreife: sichtbares Feedback, sinnvolle Defaults und Einstellungsmöglichkeiten.

**Deliverables:**
- `SettingsPage` erweitert:
  - `SnapGridSize` (12/16/24/32)
  - `EnablePegboardMode` (on/off)
  - `AutoPopOutToSecondDisplay` (default off)
- Snap-Visualisierung während des Drags (sehr dezente gepunktete Hilfslinien, nur während Drag sichtbar)
- `DockingService` unterstützt "altes" Verhalten (Layout für Nutzer, die kein Pegboard wollen)
- Fade-Animationen beim Pop-Out und Dock-Back

**Verifikation:**
```powershell
dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64
```
Manueller Test: Einstellungen ändern → Raster ändert sich live, Pop-Out-Animationen laufen.

---

### Phase 85: Test, Build & Dokumentation

**Ziel:** Block 8 wird verifiziert und dokumentiert.

**Deliverables:**
- Unit-Tests:
  - `SnapCanvas` Grid-Snap- und Resize-Mathematik
  - `WindowMessageBus` Publizieren/Subscriben
  - `PegboardService` Roundtrip Pop-Out/Dock
  - `MultiScreenLayoutService` Display-Erkennung
- `docs/adr/ADR-004-Adaptive-UI-Canvas.md`
- README-Update für Multi-Monitor-Workflow
- Vollständiger Build:

**Verifikation:**
```powershell
dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64
py -3.12 -m pytest tests -x -q --ignore=tests/test_voice.py
powershell -ExecutionPolicy Bypass -File build-installer.ps1 -SkipPyInstaller
```
Manueller End-to-End-Test:
1. Starten, Chat-Panel im Lochraster verschieben.
2. Größe ändern, skalieren, an Grid ausrichten.
3. Pop-Out-Icon klicken → Fenster auf Monitor 2.
4. Prompt senden → Pop-Out zeigt Antwort.
5. Panel zurück ins Hauptfenster ziehen → alte Position wird wiederhergestellt.
6. App neu starten → Layout bleibt erhalten.

---

## Übergabe in die 70-Phasen-Struktur

Dieser Block ist als **Block 8 (Phasen 71–85)** vorgesehen. Er kann direkt hinter Block 7 in `Tarno Plans/tarno-70-phase-masterplan.md` eingefügt werden oder, bis zur Freigabe, als eigenständiges Planungsdokument (`block-8-adaptive-ui-canvas.md`) belassen werden.
