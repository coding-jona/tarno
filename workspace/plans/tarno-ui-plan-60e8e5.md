# TARNO Control UI — Megaplan (PySide6, OVOS-Engine, System-Tray)

Dieser Plan beschreibt den schrittweisen Aufbau einer schlanken, dark-themed PySide6-Oberfläche für TARNO, die auf der bestehenden OVOS-Engine läuft, `TARNO.exe` als UI-Entry-Point nutzt, System-Tray, Status, Chat, Einstellungen und Windows-Autostart bietet und ohne die Voice-Pipeline zu verändern später um weitere Seiten erweitert werden kann.

## Ziel

- `TARNO.exe` öffnet standardmäßig die Control-UI; `--no-gui` startet den bisherigen Headless-OVOS-Engine-Modus.
- Die UI läuft im Qt-Hauptthread; die `TarnoOvosEngine` läuft in einem `QThread`/Hintergrundthread.
- System-Tray-Icon mit Kontextmenü (Open, Mute, Start/Stop, Settings, Exit).
- Hauptfenster mit Statusanzeige, Chat-Panel, Log-Ansicht, Steuerknöpfen und einem Einstellungsdialog.
- Einstellungen werden in `tarno_config.yaml` gespeichert; API-Keys bleiben per `setx` in `MISTRAL_API_KEY`/`CLAUDE_API_KEY` und werden nur angezeigt.
- Optionaler Autostart über `HKEY_CURRENT_USER\...\Run`.
- Dark TARNO-Theme, schlank, ohne Animationen.
- NSIS-Installer erstellt Desktop- und Startmenü-Verknüpfungen.

## Scope (In/Out)

### In Scope
- `tarno/__main__.py` — Entry-Point: default → UI, `--no-gui` → Headless.
- `tarno/ui/` — neues Package:
  - `app.py` — `run_ui()` startet `QApplication`, `EngineController`, `BusListener`, `ControlWindow`, `TrayIcon`.
  - `engine_controller.py` — `QObject` im `QThread`, wrappt `TarnoOvosEngine`, Slots: `start/stop`, `toggle_mute`, `send_text`.
  - `bus_listener.py` — `MessageBusClient` im UI-Thread, empfängt `speak`, `tarno.status`, `tarno.error` und gibt Qt-Signale aus.
  - `control_window.py` — Hauptfenster mit Status, Chat, Log, Start/Stop/Mute.
  - `settings_dialog.py` — Editor für `tarno_config.yaml`, API-Key-Anzeige, Autostart-Checkbox.
  - `tray.py` — `QSystemTrayIcon` + Menü.
  - `theme.py` — Dark-Stylesheet (bestehende `tarno/gui/theme.py` wiederverwenden/anpassen).
  - `widgets/` — `chat_area.py`, `status_bar.py`, `mic_button.py`, `log_view.py`.
- `tarno/core/config.py` — `UIConfig` hinzufügen (`autostart`, `start_minimized`).
- `config/default.yaml` — `ui:`-Block ergänzen.
- `tarno/voice/voice_service.py` — `tarno.status` Nachrichten emittieren, `mute`/`unmute` via `EngineController` unterstützen.
- `tarno/core/agent_service.py` — `tarno.status` für `thinking`, `ready`, `error` emittieren.
- `tarno/utils/log.py` — File-Logging nach `~/.tarno/logs/tarno.log`, `console=False` kompatibel machen.
- `tarno.spec` — `console=False`, `collect_all('PySide6')` bzw. PySide6-Hiddenimports ergänzen.
- `TARNO_Installer.nsi` — Desktop-Shortcut, Startmenü-Eintrag, ggf. Autostart-Option.
- `tarno-time-estimate-complete-60e8e5.md` — Roadmap um UI-Versionen ergänzen.

### Out of Scope
- Holographic/3D-Overlay (v2.0).
- Web-/Electron-UI.
- C#/WinUI-Frontend (ersetzt alten `tarno-winui-plan-60e8e5.md`).
- Neue LLM-/Voice-Engine (`tarno.core.engine` bzw. `service_mediator` und `workers` bleiben unverändert, aber inaktiv).

## Randbedingungen

- `QApplication` muss im Hauptthread laufen.
- `TarnoOvosEngine` darf nicht im Hauptthread blockieren (`wait_for_exit_signal` wird durch `threading.Event`/`QThread` ersetzt).
- `MessageBusClient` des UI darf mit dem lokalen OVOS-Bus (`ws://127.0.0.1:8181/core`) kommunizieren.
- `pygame`/`pyaudio` bleiben im Voice-Thread; UI initialisiert kein Audio neu.
- API-Keys werden nicht in der Config gespeichert; UI zeigt nur an, ob `MISTRAL_API_KEY`/`CLAUDE_API_KEY` gesetzt sind.
- Windows 10/11 ist primäre Zielplattform; Code bleibt aber plattformunabhängig.
- NSIS-Installer benötigt keine Admin-Rechte (HKCU Autostart).

## Architektur

```
┌─────────────────────────────────────────────────────────────┐
│  TARNO.exe                                                 │
│  ┌──────────────────────┐   ┌──────────────────────────┐   │
│  │  QApplication (main) │   │  EngineController (QThread)│   │
│  │  ControlWindow       │   │  TarnoOvosEngine.start()  │   │
│  │  TrayIcon            │   │  shutdown_event.wait()     │   │
│  │  BusListener         │   │  voice_service / bus_client│   │
│  └──────────────────────┘   └──────────────────────────┘   │
│              │                          │                   │
│              │  Qt Signals              │  MessageBus       │
│              │                          │                   │
│              ▼                          ▼                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  ovos-messagebus  (ws://127.0.0.1:8181/core)            │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

1. **`run_ui(config)`** in `tarno/ui/app.py`:
   - `QApplication` erzeugen, `setQuitOnLastWindowClosed(False)`.
   - `setup_logging` mit `log_file=~/.tarno/logs/tarno.log` aufrufen.
   - `EngineController` erzeugen, in `QThread` verschieben, `start_engine()` aufrufen.
   - `BusListener` erzeugen und verbinden.
   - `ControlWindow` + `TrayIcon` erzeugen und anzeigen.
   - `app.aboutToQuit` → `controller.stop_engine()`.

2. **`EngineController`**:
   - `self._engine = TarnoOvosEngine()`.
   - `self._shutdown_event = threading.Event()`.
   - Slot `start_engine()`: `self._engine.start()` dann `self._shutdown_event.wait()`.
   - Slot `stop_engine()`: `self._shutdown_event.set()` dann `self._engine.stop()`.
   - Slot `toggle_mute()`: `self._engine.voice_service.stop()`/`start()` (oder später feiner via `voice_service.muted`).
   - Slot `send_text(text)`: `self._engine.bus_client.emit(Message("recognizer_loop:utterance", ...))`.
   - Signale: `engine_started`, `engine_stopped`, `error`.

3. **`BusListener`**:
   - `MessageBusClient` im UI-Thread, `run_in_thread()`.
   - `on("speak", ...)` → `assistant_message` Signal.
   - `on("tarno.status", ...)` → `status_changed` Signal.
   - `on("tarno.error", ...)` → `error` Signal.

4. **Voice/Agent Status Nachrichten**:
   - `VoiceService` emittiert `Message("tarno.status", {"state": "listening" | "speaking" | "ready"})`.
   - `AgentService` emittiert `Message("tarno.status", {"state": "thinking" | "ready"})` bei Utterance und Response.

5. **Settings**:
   - `SettingsDialog` lädt `TarnoConfig.load()` (default + user), speichert in `~/.tarno/config/tarno_config.yaml`.
   - Änderungen erfordern initial einen Neustart (deutlich kennzeichnen).
   - API-Keys: read-only aus `os.environ` anzeigen.
   - Autostart: Registry-Eintrag setzen/entfernen.

6. **Tray / Autostart**:
   - `TrayIcon` mit Icon aus `tarno/ui/assets/icon.png` (oder fallback System-Icon).
   - Rechtsklick-Menü: `Open`, `Mute`, `Start/Stop Engine`, `Settings`, `Exit`.
   - Schließen des Fensters minimiert in den Tray.
   - Autostart-Checkbox in Settings schreibt `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run\TARNO` mit dem `TARNO.exe`-Pfad.

## UI-Komponenten (MVP)

| Komponente | Funktion |
|------------|----------|
| `ControlWindow` | Hauptfenster 800×600, dunkel, übersichtlich. |
| `StatusBar` | Zustand: `Bereit`, `Hört zu`, `Denkt nach`, `Spricht`, `Stumm`. |
| `ChatArea` | User- und Assistant-Nachrichten, scrollable; Eingabezeile + Senden. |
| `MicButton` | Push-to-talk / Mute-Status. |
| `LogView` | Letzte 200 Log-Zeilen aus `~/.tarno/logs/tarno.log` (tail oder `QtLogHandler`). |
| `SettingsDialog` | Reiter: Allgemein, Audio, Wake-Word, LLM, Briefing, UI. |
| `TrayIcon` | Tray-Menü + Doppelklick öffnet Fenster. |

## Phasen & Zeitaufwand

| Phase | Inhalt | Aufwand |
|-------|--------|---------|
| 1. UI-Grundgerüst | `tarno/ui/` anlegen, `app.py`, `ControlWindow`, `TrayIcon`, `theme.py`, `QApplication` | 1 Woche |
| 2. Engine-Integration | `EngineController` (QThread), `BusListener`, `__main__.py` default UI, `setup_logging` File-Log | 1–2 Wochen |
| 3. Status & Chat | Voice/Agent `tarno.status` Nachrichten, `ChatArea`, `MicButton`, `StatusBar` | 1 Woche |
| 4. Settings & Autostart | `SettingsDialog`, `UIConfig`, `config/default.yaml`, Registry-Autostart, API-Key-Anzeige | 1 Woche |
| 5. Packaging & Installer | `tarno.spec` PySide6 + `console=False`, Desktop-Shortcut, Startmenü, Testen | 1 Woche |
| 6. Polish & Stabilisierung | Fehlerbehandlung, Logging, UI-Tests, Edge Cases, Dokumentation | 1–2 Wochen |
| **Subtotal** | | **6–8 Wochen** |

## Zusätzliche realistische Kosten

- **UI-Fein-Tuning (15–25%)**: Theme-Abstimmung, Layout-Fehler, DPI/Skalierung, Fokus- und Tab-Reihenfolge.
- **Tests & Edge Cases (15–20%)**: Tray-Verhalten, Start/Stop während TTS, Mehrfachstart, `console=False` Logging, Fehler im OVOS-Thread.
- **Iteration & Feedback (10–15%)**: Anpassungen nach Bedienung, weitere Shortcuts, weitere Settings-Felder.
- **Dokumentation & Packaging (5–10%)**: Installer, README, Shortcuts.

## Gesamtschätzung

| Ansatz | Aufwand | Zeit |
|--------|---------|------|
| MVP Control UI (Tray + Status + Chat + Settings) | **6–8 Wochen** | ca. 1,5–2 Monate |
| MVP + Fein-Tuning + Tests + Packaging | **8–12 Wochen** | ca. 2–3 Monate |

## Roadmap-Integration

| Version | UI-Inhalt |
|---------|-----------|
| **v0.1** | (bereits) Headless, Voice, Memory, TTS-Cache, Tests |
| **v0.2** | **Control UI** (dieser Plan): Tray, Status, Chat, Settings, Autostart, Installer-Shortcuts |
| **v0.3** | Erweiterte UI: Dashboard, Plugins-Seite, Browser-Integration, bessere Logs, globale Hotkeys |
| **v1.0** | Production UI: Stabil, getestet, poliert, vollständige Einstellungen, Dokumentation |
| **v2.0** | Holographic/Overlay-Visual-Experience (separater Plan, erst nach v1.0) |

## Akzeptanzkriterien

- `TARNO.exe` startet ohne Konsolenfenster und öffnet die Control-UI.
- `--no-gui` startet weiterhin die Headless-OVOS-Engine.
- Tray-Icon ist sichtbar; Doppelklick öffnet das Fenster; Schließen minimiert in den Tray.
- `Start/Stop` und `Mute` schalten die Voice-Pipeline sauber.
- Texteingabe im Chat wird an `recognizer_loop:utterance` gesendet; Assistant-Antworten erscheinen im Chat.
- Status wechselt korrekt zwischen `Bereit`, `Hört zu`, `Denkt nach`, `Spricht`.
- Einstellungen werden in `tarno_config.yaml` gespeichert und nach Neustart wirksam.
- API-Keys werden aus `MISTRAL_API_KEY`/`CLAUDE_API_KEY` gelesen und nicht gespeichert.
- Autostart-Checkbox setzt/entfernt den Registry-Eintrag.
- NSIS-Installer erstellt Desktop- und Startmenü-Verknüpfungen.
- PyInstaller-Paket enthält PySide6 und startet fehlerfrei.

## Risiken

- `pygame`/`pyaudio` im QThread/Engine-Thread: muss getestet werden, ggf. Synthesizer-Init in Hauptthread vorverlegen.
- `MessageBusClient` im UI: Callbacks laufen in WebSocket-Thread, alle Updates müssen via Qt-Signals in Hauptthread gehen.
- `console=False` + `setup_logging`: `sys.stdout`/`stderr` können `None` sein, `StreamHandler` muss damit umgehen.
- PyInstaller + PySide6: Bündelgröße steigt deutlich; möglicherweise fehlende `PySide6` Plugins/Binaries.
- `ovos-messagebus` im Hintergrundthread: `wait_for_exit_signal` ist durch `Event` ersetzt, muss auf sauberes Shutdown getestet werden.

## Nächste Schritte

1. `tarno/ui/` Package und `app.py` Grundgerüst anlegen.
2. `EngineController` (QThread) mit `TarnoOvosEngine` bauen.
3. `BusListener` + `ControlWindow` + `TrayIcon` verbinden.
4. `VoiceService` und `AgentService` um `tarno.status` erweitern.
5. `SettingsDialog` und `UIConfig` implementieren.
6. `tarno.spec` und `TARNO_Installer.nsi` anpassen.
7. Build, Test, Polish.
