# TARNO WinUI 3 Desktop-App – Implementierungsplan

Wir bauen auf dem bestehenden Python-Code in `e:\Downloads\openWakeWord-0.6.0\tarno\` eine Windows-11-Fluent-Desktop-App mit WinUI 3 (C#/XAML) als Frontend und einem Python-Backend, das über gRPC kommuniziert; der Fokus liegt auf Design und Architektur-Erweiterung, ohne bereits funktionierende Funktionalitäten zu verändern oder zu zerstören.

---

## Randbedingung: Bestehende Funktionalität schützen

- **Nichts kaputt machen:** Bereits laufende Skripte und Module (`tarno_ai_master.py`, `tarno_voice_full.py`, `tarno_assistant.py`, `app.py`, bestehende Voice- und AI-Logik) bleiben unverändert funktionsfähig.
- **Nur erweitern/verlagern:** Neue Architektur (Services, Event-Bus, DI) wird **zusätzlich** neben den bestehenden Einstiegspunkten aufgebaut, nicht durch Umbau derer interner Abläufe.
- **Fallback erhalten:** Sollte das neue WinUI-Frontend nicht gestartet werden können, müssen die bisherigen Startskripte (`start_tarno.bat`, `tarno.bat`) weiterhin den klassischen Voice-Assistant ausführen.
- **Design-First:** Die aktuelle Arbeitsphase konzentriert sich auf das Designsystem, die UI-Struktur und die lose Kopplung von Frontend und Backend – nicht auf die Neuschreibung bereits funktionierender Fähigkeiten.

---

## Ausgangslage & Ziele

- **Bestehender Code:** `e:\Downloads\openWakeWord-0.6.0\tarno\` enthält bereits eine Paketstruktur (`app.py`, `tarno_assistant.py`, leere Module für `ai/`, `voice/`, `desktop/`, `browser/`, `plugins/`, `utils/` etc.) und lauffähige Skripte (`tarno_ai_master.py`, `tarno_voice_full.py`).
- **Ziel:** Ergänzen und Strukturieren der Python-Logik in eine saubere Service-Layer-Architektur und ein neues WinUI 3-Frontend als Hauptfenster, ergänzt um ein Designsystem mit BuildMC-Farben/Cyan-Akzent, 4px-Radius und Fluent-Prinzipien – ohne bestehende, funktionierende Einstiegspunkte zu verändern.

---

## 1. Architektur-Fundament (Python)

**Ziel:** Bestehende Fähigkeiten (Wake-Word, Speech-to-Text, Claude, TTS, PC-Steuerung) in neue Services **verlagern/extrahieren**, ohne die originalen Einstiegspunkte zu verändern; die Services werden über einen Event-Bus gekoppelt.

- **Service Layer** (`tarno/services/`):
  - `AudioService` – Mikrofon/Lautsprecher, Lautstärke.
  - `VoiceService` – STT (Google Speech / Whisper-Fallback).
  - `WakeWordService` – openWakeWord-Integration, aktiviert `VoiceService`.
  - `AIService` – Anthropic-Claude-Client, Prompt-Templates, Caching.
  - `IntentParser` – lokale Regel/Regex-Engine für simple Befehle ("Spotify öffnen", "Lautstärke 30%"), um API-Aufrufe zu sparen.
  - `DesktopAutomationService` – pyautogui, pywinauto, Fenster/Dateisystem.
  - `BrowserService` – WebView2/Steuerung via Playwright oder eingebetteter Browser.
  - `MemoryService` – SQLite + Embeddings-Cache für Konversationsverlauf.
  - `PluginService` – DLL/Python-Plugins laden, Lifecycle verwalten.
  - `ConfigService` / `LoggingService` – YAML-Settings, zentrales Logging.
- **Event-Bus** (`tarno/core/event_bus.py`): Async Pub/Sub; UI- und Service-Events (z. B. `Voice.Listening`, `AI.Thinking`, `Task.Progress`).
- **Domain-Modelle** (`tarno/core/models.py`): `Task`, `Command`, `Intent`, `Message`, `Plugin`.
- **Dependency Injection** (`tarno/core/container.py`): Microsoft.Extensions.DependencyInjection-artiger Container oder Python-IoC-Container; Services werden konstruktorinjiziert.
- **Tool-Router** (`tarno/core/router.py`): Entscheidet, ob Anfrage lokal (`IntentParser` → `DesktopService`) oder an Claude geht; simple Kommandos ohne API-Aufruf.
- **gRPC-API** (`tarno/grpc/`): Protobuf-Definition für Streaming-Methoden (Voice-Audio, Chat-Nachrichten, Task-Updates, Events). C#-Client generieren.

---

## 2. WinUI 3-Frontend (C# / XAML / Windows App SDK)

**Ziel:** Native `.exe`-App mit Windows-11-Fluent-Look, Mica/Acrylic, 4px-Corners, Cyan-Akzent.

- **Projekt:** `TARNO.sln` im Ordner `E:\Downloads\openWakeWord-0.6.0\src\TARNO.UI\` (einziger gültiger Pfad).
- **UI-Struktur:**
  - `MainWindow` mit Sidebar (Navigation), Topbar, Content-Frame, Statusbar.
  - Seiten: `DashboardPage`, `ChatPage`, `VoicePage`, `TasksPage`, `PluginsPage`, `MemoryPage`, `BrowserPage`, `SettingsPage`, `LogsPage`.
- **Designsystem** (`TARNO.UI\Styles\`):
  - `Colors.xaml` – Tokens: `ColorBackgroundBase`, `ColorBackgroundSubtle`, `ColorActionPrimary`, `ColorTextPrimary`, `ColorTextSecondary`, `ColorSuccess`, `ColorWarning`, `ColorError`.
  - `Typography.xaml`, `Spacing.xaml`, `CornerRadius.xaml`, `Shadows.xaml`.
  - Cyan-Akzent: `#0BC7FF`; dunkle Neutralpalette: `#111111`–`#555555`; hoher Kontrast.
- **Wiederverwendbare Komponenten:**
  - `SidebarItem`, `TARNOCard`, `TARNOButton` (Primary/Secondary), `TARNOToggleSwitch`, `TARNOComboBox`, `ChatBubble`, `CircularProgress` (HUD-Ring), `VoiceStatusRing` (Idle/Listening/Thinking).
- **TARNO HUD-Elemente:**
  - Subtile, animierte Statusringe (Pulsieren bei Listening/Thinking), keine Neon-Effekte.
  - Voice-Button mit 3 Zuständen (Idle, Listening, Thinking).
- **Accessibility:** ARIA-äquivalente XAML-Labels, Tab-Navigation, hoher Kontrast, optionale Hochkontrast-Styles.

---

## 3. UI ↔ Backend Integration

- **gRPC-Client** in C# generiert aus `tarno.proto`.
- **Kommunikationsmuster:**
  - UI sendet Befehle an den Event-Bus (nicht direkt an Services).
  - Backend streamt Events zurück (Voice-Zustand, Task-Fortschritt, Chat-Antworten, Logs).
- **Offline-Modus:** Lokale Intent-Erkennung und Systembefehle funktionieren auch ohne Claude.
- **Task-Queue:** Lang laufende Aktionen (Browser-Recherche, Dateioperationen) asynchron verarbeiten, Fortschritt im UI anzeigen.

---

## 4. Phasen & Reihenfolge

| Phase | Inhalt | Ziel-Dauer |
|-------|--------|------------|
| **1. Fundament** | Protobuf-Schema, Event-Bus, DI-Container, Domain-Modelle, Logging/Config in Python | 1–2 Sessions |
| **2. Backend-Services** | Bestehende Logik aus den lauffähigen Skripten in neue Services extrahieren/verlagern, Originalskripte bleiben erhalten | 2–3 Sessions |
| **3. gRPC-Brücke** | Python-gRPC-Server + C#-Client, Streaming-Tests | 1 Session |
| **4. WinUI-Skeleton** | Projekt anlegen, MainWindow, Navigation, Seiten-Routing | 1 Session |
| **5. Designsystem** | Colors, Typography, Spacing, Radius, Shadows, erste Komponenten | 1 Session |
| **6. GUI-Seiten** | Dashboard, Chat, Voice, Tasks, Plugins, Settings, Logs, Browser (optional) | 2–3 Sessions |
| **7. Integration** | End-to-End: Spracheingabe → Intent → Aktion → UI-Feedback | 2 Sessions |
| **8. Polish & QA** | Animationen, Fehlerbehandlung, Tray/Autostart, Installer-Setup, Tests | 2 Sessions |

---

## 5. Nächste konkrete Schritte

1. **Bestandsaufnahme:** Inhalt der bestehenden `tarno/*.py`-Dateien analysieren (`app.py`, `tarno_assistant.py`, `tarno_ai_master.py`, `tarno_voice_full.py`), um nutzbare Logik zu identifizieren.
2. **Event-Bus + DI-Container** in Python implementieren.
3. **Protobuf-Schema** (`tarno.proto`) für Chat, Voice-Events, Task-Updates und Logs definieren.
4. **WinUI 3-Projekt** anlegen und C#-gRPC-Client generieren.
5. **Designsystem-Dateien** (`Colors.xaml`, `Typography.xaml`) erstellen.
6. **Erste funktionierende Seite** bauen: Chat-Seite mit Event-Stream vom Backend.

---

## 6. Offene Punkte (zu klären vor Phase 1)

- **BuildMC-Assets:** Gibt es Screenshots/Design-Vorlagen im Projektordner, die als Farb-/Layout-Referenz genutzt werden sollen? Wenn ja, bitte Pfad nennen.
- **Claude-Key:** Wird ein Anthropic-API-Key bereitgestellt oder mit einem Mock-Service entwickelt?
- **Voice-Engine:** Soll `SpeechRecognition` (Google, online) oder `openai-whisper` (lokal) primär genutzt werden? Der bestehende Code nutzt beides.
- **Distributionsform:** Ziel ist ein eigenständiges `.exe` / MSIX? Soll der Installer im bestehenden NSIS-Skript (`TARNO_Installer.nsi`) integriert werden?

---

## 7. Dateien/Ordner-Struktur (Ziel)

```text
e:\Downloads\openWakeWord-0.6.0\
├── tarno\                          # Python-Backend
│   ├── core\                        # Event-Bus, DI, Models, Router
│   ├── services\                    # Alle Hintergrunddienste
│   ├── grpc\                        # Protobuf + Server
│   ├── plugins\                     # Plugin-Interface + Beispiel-Plugins
│   ├── utils\                       # Hilfsfunktionen
│   ├── tests\                       # pytest-Tests
│   └── main.py                       # Backend-Einstiegspunkt
├── src\TARNO.UI\                   # WinUI 3 C#-Frontend
│   ├── TARNO.UI.csproj
│   ├── MainWindow.xaml
│   ├── Pages\                        # Dashboard, Chat, Voice, ...
│   ├── Styles\                       # Colors, Typography, Shadows, ...
│   ├── Controls\                     # Wiederverwendbare Komponenten
│   ├── Services\                     # gRPC-Client, Event-Bridge
│   └── ViewModels\                   # MVVM-ViewModels
├── tarno.proto                      # gRPC-Schema
└── TARNO.sln
```

---

## Zusammenfassung

Zuerst stabilisieren wir die Python-Architektur (Event-Bus, DI, Services, gRPC), dann bauen wir ein WinUI 3-Frontend mit Fluent-Design und modularer Navigation, das über gRPC mit dem Backend kommuniziert. Der erste sichtbare Meilenstein ist eine Chat-Seite mit Live-Events vom Backend, gefolgt von Dashboard, Voice-HUD, Tasks und Plugin-Manager.
