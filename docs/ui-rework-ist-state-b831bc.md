# TARNO UI-Rework — Ist-Zustand-Report

Stand: 2026-07-12 · Plan: `tarno-hologram-overlay-rework-b831bc.md`

## 1. WinUI-3-App (`src/TARNO.UI/`)

### Pages

| Seite | Datei | Zustand |
|-------|-------|---------|
| Chat | `Pages/ChatPage.xaml` | Vollständig mit Nachrichtenliste, Eingabe, Voice-Button; Code-Behind sendet Text an gRPC. |
| Dashboard | `Pages/DashboardPage.xaml` | Platzhalter-Seite, kaum Inhalt. |
| Voice | `Pages/VoicePage.xaml` | Enthält `VoiceStatusRing`; zeigt Status und Toggle-Button; kann `VoiceCommand` senden. |
| Tasks | `Pages/TasksPage.xaml` | Platzhalter. |
| Plugins | `Pages/PluginsPage.xaml` | Etwas mehr Inhalt (ListView), aber keine echten Plugins. |
| Memory | `Pages/MemoryPage.xaml` | Platzhalter. |
| Browser | `Pages/BrowserPage.xaml` | Platzhalter. |
| Models | `Pages/ModelsPage.xaml` | Platzhalter. |
| Settings | `Pages/SettingsPage.xaml` | Grundlegende Einstellungen, noch kein Hologram-Tab. |
| Logs | `Pages/LogsPage.xaml` | Zeigt Logs aus `MainViewModel.Logs` an. |

### Controls

| Control | Datei | Zweck |
|---------|-------|-------|
| `VoiceStatusRing` | `Controls/VoiceStatusRing.xaml` | 96×96 Ring mit 3 Zuständen (Idle, Listening, Thinking). Einfacher Puls, keine Animation. |
| `ChatBubble` | `Controls/ChatBubble.xaml` | User/Assistant Chat-Blasen. |
| `TARNOCard` | `Controls/TARNOCard.xaml` | Wiederverwendbare Karte. |
| `SidebarItem` | `Controls/SidebarItem.xaml` | Navigationseintrag mit Icon/Label. |

### MainWindow

`MainWindow.xaml` hat `MicaBackdrop Kind="BaseAlt"`, 1280×800 Größe, Sidebar mit 10 Seiten, Content-Frame, Topbar/Statusbar. Keine Always-on-top- oder Overlay-Logik. `MainWindow.xaml.cs` initialisiert `MainViewModel`, Dispatcher, Navigation.

## 2. Styles-System

| Datei | Inhalt | Fehlend für Hologramm |
|-------|--------|----------------------|
| `Colors.xaml` | Primitive + semantische Farben, Cyan-Akzent #0BC7FF. | Glow-Brushes, ConicGradient, Statusfarben Idle/Listening/Processing/Speaking/Error. |
| `Typography.xaml` | Segoe UI Variable, 6 Größen, Text-Styles. | Monospace-Label für Overlay-Status. |
| `Shadows.xaml` | 5 `ThemeShadow`-Token. | Glow-Shadows (Cyan/Amber), Elevation-Token für Overlay-Flyout. |
| `Spacing.xaml` | Margin/Padding-Tokens. | Overlay-spezifische Radii (20 px Flyout, 999 px Buttons). |
| `ControlOverrides.xaml` | Globale Button/TextBox-Styles. | Hologram-Flyout-/Menü-Styles. |

## 3. gRPC-Backend-Verbindung

Backend: `start_tarno_winui_backend.py` → `tarno/grpc/server.py` auf Port 50051.

| Event | Proto-Typ | Aktuelle Zustände | Geplant |
|-------|-----------|------------------|---------|
| Chat | `ChatMessage` | user/assistant | unverändert |
| Status | `StatusUpdate` | Text-Status | unverändert |
| Voice | `VoiceStateUpdate` | `VOICE_IDLE`, `VOICE_LISTENING`, `VOICE_THINKING` | + `VOICE_PROCESSING`, `VOICE_SPEAKING`, `VOICE_ERROR` |
| Logs | `LogEntry` | Level/Message | unverändert |
| Task | `TaskUpdate` | pending/running/... | unverändert |
| Thinking | `ThinkingUpdate` | bool | unverändert |
| SystemInfo | `SystemInfo` | os/cpu/memory/... | unverändert |

`GrpcClientService` in `src/TARNO.UI/Services/GrpcClientService.cs` empfängt alle Events und dispatched auf den UI-Thread.

## 4. Legacy-UI-Referenzen

| Datei | Referenz | Aktion im Rework |
|-------|----------|------------------|
| `tarno/__main__.py` | Default-Pfad startet `tarno.ui.app.run_ui()` | Umstellen auf WinUI-Startorchester, `--legacy-ui` für PySide6. |
| `tarno/ui/app.py` | `ControlWindow`, `TrayIcon`, `OverlayWindow` (nicht instanziiert) | `OverlayWindow`-Referenz entfernen; PySide6-Pfad bleibt Fallback. |
| `tarno/ui/control_window.py` | PySide6-Hauptfenster | Nur `--legacy-ui` aktiv. |
| `tarno/ui/overlay_window.py` | PySide6-Overlay, toter Code | Als deprecated markieren. |
| `start_tarno.bat` | `py -3.12 -m tarno` | Auf `--legacy-ui` umstellen oder neuen WinUI-Launcher nutzen. |
| `start_tarno_winui.bat` | Startet Backend + WinUI-Exe manuell | Durch neuen Python-Launcher ersetzen. |
| `installer/dist/artifacts/.../overlay_window.py` | Alte Build-Kopie | Beim nächsten Installer-Build neu erzeugen. |
| `tarno/gui/` | BuildMC-Clone | Frozen-Pfad, nicht weiterentwickeln. |

## 5. Offene Punkte vor Phase 2

1. `tarno/grpc/tarno.proto` muss um 3 neue Voice-Zustände erweitert werden; C#-Stubs werden automatisch durch `dotnet build` neu generiert.
2. `config/default.yaml` braucht `ui.backend: winui` und den `winui:`-Block.
3. `TARNO.UI.exe` existiert bereits unter `src/TARNO.UI/bin/x64/Debug/net8.0-windows10.0.19041.0/`, muss aber nicht automatisch neu gebaut werden.
4. EchoProtection (`tarno/voice/echo_protection.py`) ist vorhanden, aber nicht in `tarno/core/engine.py` aktiv; muss in Phase 5 verdrahtet werden.

## 6. Empfohlene erste Schritte

1. `config/default.yaml` + `tarno/core/config.py` erweitern.
2. `tarno/grpc/tarno.proto` erweitern und Build laufen lassen.
3. `tarno/ui/winui_launcher.py` + `tarno/__main__.py` anpassen.
4. `Styles/Hologram.xaml` und `Controls/HologramOverlay.xaml` anlegen.
