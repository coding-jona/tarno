# TARNO – Technischer Schulden-Katalog

**Stand:** 2026-07-13 | **Phase:** 4 – Alle Prio-1-Punkte behoben, Prio-2/3 offen

## Legende

- **Prio 1 (Kritisch):** Blockiert Release oder verursacht Crashes
- **Prio 2 (Hoch):** Deutliche Qualitätsminderung, sollte vor Release behoben werden
- **Prio 3 (Mittel):** Verbesserung, kann nach Release erfolgen

---

## Prio 1 — Kritisch

### TD-001: Kein Atomic Config Write — ✅ BEHOBEN (2026-07-13)
**Datei:** `tarno/core/config.py:283-325`  
**Problem:** `config.save()` schreibt direkt in die Zieldatei. Bei Crash während des Schreibens ist die Config korrupt.  
**Lösung:** `save()` schreibt in eine Temp-Datei im selben Verzeichnis (`tempfile.mkstemp`), `fsync`, legt ein `.bak`-Backup der bestehenden Datei an und ersetzt dann atomar via `os.replace()`. Bei Fehler wird die Temp-Datei aufgeräumt, die Exception weitergereicht. `_load_yaml` fällt bei korrupter Hauptdatei automatisch auf `.bak` zurück.  
**Getestet:** `tests/test_config_safety.py` (12 Tests, u.a. Crash-Simulation während Write).  
**Phase:** 2

### TD-002: VoiceController ohne Crash-Recovery — ✅ BEHOBEN (2026-07-13)
**Datei:** `tarno/core/voice_controller.py`  
**Problem:** `_run_loop` fängt Exception am Ende, aber startet nicht neu. Audio-Stream bleibt gestoppt wenn Recognition fehlschlägt.  
**Lösung:** Formale `VoiceState`-Zustandsmaschine, `_run_loop_safe()` fängt alle Exceptions und startet die Schleife nach kurzer Pause neu, plus separater `_watchdog`-Thread der über Heartbeat/Timeout (120s) einen kompletten Neustart des Voice-Threads erzwingt falls die Schleife hängt (nicht nur crasht). `AudioStream` nutzt `pause()/resume()` statt `stop()/start()`, damit die PyAudio-Instanz über Interaktionen hinweg erhalten bleibt.  
**Getestet:** `tests/test_voice_pipeline.py` (21 Tests, u.a. Pause/Resume-Zyklen, Recovery).  
**Phase:** 2

### TD-003: gRPC-Client ohne Auto-Reconnect — ✅ BEHOBEN (2026-07-13)
**Datei:** `src/TARNO.UI/Services/GrpcClientService.cs`  
**Problem:** `ConnectAsync` wird einmal aufgerufen. Kein Retry bei Connection-Loss.  
**Lösung:** `ReadLoopWithReconnectAsync` fängt `RpcException`/`Unavailable`/Stream-Ende ab und reconnected mit exponentiellem Backoff (1s → max. 30s). `OnConnectionStateChanged`- und `OnStatusChanged`-Events informieren die UI ("Reconnect in Xs (Versuch N)...", "Verbunden"). Sende-Methoden (`SendChatAsync` etc.) setzen bei Fehlern den Zustand auf getrennt statt zu werfen.  
**Phase:** 2

### TD-004: API-Key-Handling nicht durchgängig — ✅ BEHOBEN (2026-07-13)
**Dateien:** `tarno/ai/mistral_client.py`, `gemini_client.py`, `groq_client.py`, `huggingface_client.py`, `claude_client.py`, `tarno/ai/factory.py`  
**Problem:** Provider lasen API-Keys direkt aus `os.environ`. SecretsVault existierte, wurde aber nicht von allen Providern genutzt.  
**Lösung:** Alle 5 Provider akzeptieren jetzt `api_key`-Parameter, `factory.py` löst ihn zentral über `SecretsVault` auf (mit Env-Fallback). First-Start-Wizard (`FirstStartWizardDialog`) + Settings-KI-Tab für Key-Eingabe.  
**Phase:** 3

### TD-005: PySide6 im PyInstaller-Bundle (92 MB) — ✅ BEHOBEN (2026-07-13)
**Datei:** `tarno.spec`  
**Problem:** PySide6 wird als Hidden-Import eingebunden, obwohl WinUI 3 das primäre Frontend ist. Kostet 92 MB im Installer.  
**Lösung:** PySide6/shiboken6 aus `hiddenimports` entfernt (ADR-002), mit erklärendem Kommentar an der Stelle.  
**Phase:** 2

---

## Prio 2 — Hoch

### TD-006: Doppelter UI-Stack (PySide6 + WinUI) — ✅ BEHOBEN (2026-07-13)
**Dateien:** `tarno/ui/` (13 Python-Dateien), `tarno/gui/`, `src/TARNO.UI/` (C#/XAML)  
**Problem:** Zwei vollständige UI-Implementierungen werden gepflegt. PySide6-UI veraltet, aber nicht als solche gekennzeichnet — Risiko, dass künftige Agenten dort neue Features bauen.  
**Lösung:** Beide Pakete (`tarno/ui/__init__.py`, `tarno/gui/__init__.py`) tragen jetzt einen expliziten Deprecated-Hinweis im Modul-Docstring, der auf WinUI 3 als primäres Frontend verweist. Kein Code-Verhalten geändert (leere `__init__.py` zuvor).  
**Phase:** 2

### TD-007: OVOS-Dependencies im Standard-Bundle — ✅ BEHOBEN (2026-07-13, via TD-020)
**Datei:** `requirements.txt`, `requirements-ovos.txt`, `tarno.spec`  
**Problem:** 13 OVOS-Packages nur für `--no-gui` Modus. ~100 MB im Bundle.  
**Lösung:** OVOS-Pakete leben ausschließlich in `requirements-ovos.txt` (siehe TD-020), `requirements.txt` und `tarno.spec`-Hiddenimports sind frei davon.  
**Phase:** 2

### TD-008: Hardcoded Deutsche Strings
**Dateien:** Alle Python-Module und XAML-Seiten  
**Problem:** UI-Strings und Fehlermeldungen sind direkt im Code. Keine i18n-Architektur.  
**Lösung:** Resource-Dateien (.resw für WinUI, gettext/json für Python). Erst relevant wenn Mehrsprachigkeit geplant.  
**Phase:** 7+ (nach Release)

### TD-009: SettingsPage schreibt JSON, Config liest YAML — ⚠️ NEU BEWERTET (2026-07-13)
**Dateien:** `src/TARNO.UI/Pages/SettingsPage.xaml.cs`, `tarno/core/config.py`  
**Problem (Original-Annahme):** WinUI-Settings werden als JSON gespeichert (`%LocalAppData%\TARNO\settings.json`), Backend liest YAML (`~/.tarno/config/tarno_config.yaml`). Zwei getrennte Config-Systeme.  
**Befund bei Prüfung:** Die einzigen von `SettingsPage` verwalteten Felder sind `Theme`, `StartupPage`, `AutoStart` — alle drei sind rein WinUI-lokale Concerns ohne Backend-Äquivalent. `TarnoConfig.theme` (Python) wird ausschließlich von der PySide6-Legacy-GUI gelesen (`tarno/ui/`, `tarno/gui/`), nicht vom WinUI/gRPC-Pfad. Die beiden Config-Systeme überschneiden sich aktuell in keinem Feld — kein Lost-Update- oder Inkonsistenz-Risiko in der Praxis. API-Keys (das einzige sicherheitsrelevante Setting) laufen bereits korrekt über gRPC → `SecretsVault` (TD-004).  
**Entscheidung:** Kein gRPC-Settings-Sync-RPC bauen, solange kein Feld tatsächlich in beiden Frontends gebraucht wird — das wäre Vorab-Abstraktion ohne aktuellen Bedarf. Neu bewerten, sobald ein Setting eingeführt wird, das Backend *und* WinUI betrifft.  
**Phase:** 4 (zurückgestellt, kein Code-Risiko)

### TD-010: Installer ohne Post-Install-Validierung — ✅ BEHOBEN (2026-07-13)
**Datei:** `TARNO_Installer.nsi`  
**Problem:** NSIS-Installer prüfte nicht, ob alle kritischen Dateien nach Installation vorhanden sind.  
**Lösung:** `ValidateInstallation`-Funktion prüft nach dem Kopieren: `TARNO.UI.exe`, `tarno.exe`, .NET-8-Runtime-Registrierung, Registry-Eintrag, Startmenü-Verknüpfung, Uninstaller — sammelt fehlende Punkte in einer einzigen verständlichen Meldung statt stillem "Erfolg".  
**Phase:** 3

### TD-011: WinUI-Designsystem inkonsistent
**Dateien:** `src/TARNO.UI/Styles/Colors.xaml`, `GlassStyles.xaml`  
**Problem:** Farben und Styles wurden mehrfach umgebaut (erst Glass, dann BuildMC, jetzt eigenständig). Einige Seiten nutzen noch alte Token-Namen.  
**Lösung:** Vollständiges Designsystem mit neuen TARNO-Tokens in Phase 5.  
**Phase:** 5

---

## Prio 3 — Mittel

### TD-012: Repository heißt noch `openWakeWord-0.6.0`
**Problem:** Verwirrend. Ist kein Fork mehr, sondern TARNO.  
**Lösung:** Umbenennen (ADR-003). Erfordert Anpassung aller absoluten Pfade.  
**Phase:** 8

### TD-013: Logging nicht vereinheitlicht
**Problem:** Python-Backend nutzt `logging`, WinUI hat `InteractionLogger.cs`, kein zentrales Log-Viewing.  
**Lösung:** Log-Aggregation: Backend-Logs via gRPC an UI senden, UI zeigt alle Logs in einem Panel.  
**Phase:** 4

### TD-014: Conversation Manager hat keinen Token-Count
**Datei:** `tarno/ai/conversation.py`  
**Problem:** History wird nur nach Anzahl beschnitten (`max_history`), nicht nach Token-Count. Kann zu API-Fehlern führen.  
**Lösung:** Token-Counting pro Provider (tiktoken oder Provider-eigener Tokenizer).  
**Phase:** 7

### TD-015: Test-Framework nicht installiert in Prod-Umgebung
**Problem:** `pytest` ist nicht in `requirements.txt`. Tests können nicht im gebundenen Package laufen.  
**Lösung:** `requirements-dev.txt` erstellen mit pytest, coverage, etc.  
**Phase:** 1

### TD-016: `_err.txt`, `_out.txt`, etc. im Repository-Root
**Problem:** Debug-Ausgabe-Dateien liegen im Root und werden nicht per .gitignore ignoriert.  
**Lösung:** `.gitignore` aktualisieren, Dateien entfernen.  
**Phase:** 1

### TD-017: First-Start-Wizard nicht in WinUI integriert — ✅ BEHOBEN (2026-07-13)
**Datei:** `tarno/first_start/` (PySide6-basiert)  
**Problem:** Der First-Start-Wizard nutzte PySide6. Sollte im WinUI-Frontend als eigene Page/Dialog existieren.  
**Lösung:** `FirstStartWizardDialog` (ContentDialog) in `src/TARNO.UI/Dialogs/`, ausgelöst beim ersten erfolgreichen gRPC-Connect wenn kein Provider konfiguriert ist (`MainWindow.OnFirstConnected`, `SettingsStore.FirstRunWizardCompleted`-Flag). Die PySide6-Variante in `tarno/first_start/` bleibt als Fallback für `--legacy-ui` bestehen.  
**Phase:** 3

---

## Funde aus dem Security-/Bug-/Effizienz-Gegencheck (2026-07-13)

Ab sofort wird jede Phasen-Verifikation zusätzlich um einen Code-Gegencheck (Schwachstellen, Bugs, Lints, Ineffizienz, indirekte Folgeprobleme) ergänzt — nicht nur ein Abgleich "steht es im Plan / existiert die Datei". Die folgenden Funde stammen aus dem ersten Durchlauf dieser Methode.

### TD-018: gRPC-Server auf Wildcard-Adresse statt Loopback gebunden — ✅ BEHOBEN (2026-07-13)
**Datei:** `tarno/grpc/server.py` (`TarnoGrpcServer.start`)  
**Problem:** `add_insecure_port(f"[::]:{port}")` bindet auf alle Netzwerk-Interfaces. Der Dienst hat keinerlei Authentifizierung — inkl. der neuen `SetApiKey`-RPC, die in den SecretsVault schreibt. Jedes Gerät im selben lokalen Netzwerk konnte theoretisch API-Keys überschreiben oder Chat-Eingaben injizieren.  
**Lösung:** Bindung auf `127.0.0.1` + `[::1]` (Loopback-only). Der WinUI-Client verbindet ohnehin immer über `localhost`, keine Verhaltensänderung im Normalbetrieb.  
**Phase:** 3 (Nachtrag)

### TD-019: SecretsVault `encrypted_file`-Backend ohne Schreib-Locking
**Datei:** `tarno/security/secrets.py` (`_EncryptedFileStorage.set`)  
**Problem:** Read-Modify-Write der gesamten verschlüsselten JSON-Datei ohne Datei-Lock. Zwei nahezu gleichzeitige `SetApiKey`-Aufrufe (z.B. First-Start-Wizard + Settings-Tab) könnten sich gegenseitig überschreiben (Lost Update).  
**Lösung (offen):** Datei-Lock (z.B. `msvcrt.locking` auf Windows) oder Serialisierung über die bereits vorhandene `asyncio.Lock` in `TarnoGrpcBridge` sicherstellen, dass `SetApiKey`-Aufrufe nicht parallel laufen.  
**Risiko-Einschätzung:** Niedrig — Standard-Backend ist `keyring`, nicht `encrypted_file`; nur relevant wenn Nutzer explizit auf `encrypted_file` umstellt.  
**Phase:** 3 (Nachtrag)

### TD-020: `requirements.txt` enthielt OVOS-Pakete entgegen ADR-002 — ✅ BEHOBEN (2026-07-13)
**Datei:** `requirements.txt`  
**Problem:** ADR-002 entschied, OVOS-Pakete in eine separate `requirements-ovos.txt` auszulagern; `tarno.spec` wurde entsprechend angepasst, `requirements.txt` aber nicht — ein Standard-`pip install -r requirements.txt` zog weiterhin alle 5 OVOS-Pakete.  
**Lösung:** OVOS-Zeilen nach `requirements-ovos.txt` verschoben. `tarno/__main__.py` fängt jetzt zusätzlich `ImportError` beim `--no-gui`-Start ab und zeigt eine verständliche Installationsanleitung statt eines rohen Tracebacks.  
**Phase:** 3 (Nachtrag)

### TD-021: AudioStream hatte keinen echten Geräte-Fallback — ✅ BEHOBEN (2026-07-13)
**Datei:** `tarno/voice/audio_stream.py`  
**Problem:** `restart()` versuchte nur das gleiche (Standard-)Gerät erneut zu öffnen. Fällt das konfigurierte Mikrofon dauerhaft weg (z.B. USB-Headset getrennt), blieb der Stream tot, obwohl der Plan (Phase 2) explizit "AudioStream mit Device-Fallback" als Ergebnis nennt.  
**Lösung:** `_open_stream_locked` versucht zuerst das zuletzt funktionierende Gerät, iteriert bei Fehlschlag über alle Eingabe-fähigen PortAudio-Geräte (`maxInputChannels > 0`) und merkt sich das erste funktionierende als neuen Standard.  
**Phase:** 2 (Nachtrag)

### TD-022: ADR-001 empfahl verworfene WebView2-Hybrid-Strategie — ✅ BEHOBEN (2026-07-13, Dokumentation)
**Datei:** `docs/adr/ADR-001-UI-Framework.md`  
**Problem:** Die ADR empfahl WebView2 als Escape-Hatch für komplexe Visualisierungen (Voice-Orb). In der Praxis rendert WebView2 in dieser WinUI3+Layered-Window-Umgebung nachweislich nichts (getestet, verworfen zugunsten von reinem XAML). Ohne Korrektur hätte ein künftiger Agent denselben bereits widerlegten Ansatz erneut versucht.  
**Lösung:** ADR-001 um "Update 2026-07-13" ergänzt, das den Fehlschlag und die tatsächlich funktionierende Lösung (reine XAML-`Ellipse`-Elemente) dokumentiert.  
**Phase:** 1 (Nachtrag)

### TD-023: First-Start-Wizard verschluckte fehlgeschlagene Key-Speicherung — ✅ BEHOBEN (2026-07-13)
**Datei:** `src/TARNO.UI/Dialogs/FirstStartWizardDialog.xaml.cs`  
**Problem:** `OnPrimaryButtonClick` rief `SetApiKeyAsync` auf, ignorierte aber das `(bool Success, string Message)`-Ergebnis vollständig. Schlug das Speichern fehl (z.B. Backend noch nicht verbunden, Keyring-Fehler), schloss sich der Dialog trotzdem als „Fertig" — der Nutzer glaubt, der Key sei gespeichert, obwohl er es nicht ist. Die parallele Implementierung in `SettingsPage.xaml.cs` (`OnSaveApiKeyClick`) hatte diese Fehlerbehandlung bereits korrekt — Inkonsistenz zwischen den beiden Eingabewegen für denselben Vorgang.  
**Lösung:** Fehlschläge werden gesammelt; gibt es welche, bleibt der Dialog offen (`args.Cancel = true`) und zeigt sie in einem neuen `ErrorText`-Element an, statt stillschweigend zu schließen.  
**Phase:** 3 (Nachtrag)

### TD-024: SecretsVault.get() propagierte Backend-Exceptions ungefangen — ✅ BEHOBEN (2026-07-13)
**Datei:** `tarno/security/secrets.py` (`SecretsVault.get`)  
**Problem:** `_EncryptedFileStorage.get()` wirft `RuntimeError`, wenn `TARNO_MASTER_KEY` fehlt oder die Datei nicht entschlüsselt werden kann. `SecretsVault.get()` fing das nicht ab — vor der Factory-Refaktorierung (TD-004) wurde der Vault kaum zentral genutzt, seit `factory.py` **jede** Provider-Erstellung darüber leitet, hätte ein falsch konfiguriertes `encrypted_file`-Backend die gesamte Provider-Initialisierung mit einer rohen Exception zum Absturz gebracht statt nur "Key nicht gefunden" zu melden.  
**Lösung:** `SecretsVault.get()` fängt Backend-Exceptions jetzt ab, loggt sie und fällt auf den Env-Var-Fallback zurück — konsistent mit dem bereits vorhandenen Verhalten von `_KeyringStorage.get()`.  
**Phase:** 3 (Nachtrag)

### TD-025: Permission-Bestätigung im gRPC-Backend hing auf `input()` statt WinUI-Dialog — ✅ BEHOBEN (2026-07-13)
**Dateien:** `tarno/core/permission_service.py`, `tarno/core/command_tool.py`, `tarno/grpc/server.py`, `tarno/grpc/tarno.proto`, `src/TARNO.UI/Services/GrpcClientService.cs`, `src/TARNO.UI/ViewModels/MainViewModel.cs`, `src/TARNO.UI/Dialogs/PermissionDialog.xaml(.cs)`, `src/TARNO.UI/MainWindow.xaml.cs`  
**Problem:** `execute_command` ist im echten (nicht Mock-)`TarnoEngine` registriert, das der gRPC/WinUI-Backend-Prozess nutzt. `CommandTool` verdrahtete `PermissionService` aber standardmäßig mit einer Qt-oder-Konsole-Bestätigungskette (`create_default_confirmation(prefer_qt=True)`). Im headless-asyncio-gRPC-Prozess gibt es weder eine laufende Qt-Event-Loop noch eine angehängte Konsole — ein MEDIUM/HIGH-Risk-Befehl hätte den Executor-Thread lautlos für immer auf `input()` hängen lassen (kein Absturz, kein Log, einfach nichts). Genau die Lücke, die Phase 4 explizit als "Permission-Dialog als WinUI-ContentDialog (nicht Console-Input)" benennt.  
**Lösung:** Neue `PermissionRequest`/`PermissionResponse`-Proto-Messages ermöglichen einen Round-Trip über den bestehenden bidirektionalen gRPC-Stream: `TarnoGrpcBridge.request_permission_sync()` blockiert den (unkritischen) Executor-Thread mit einem `concurrent.futures.Future` (Timeout 120s, danach automatische Ablehnung), broadcastet eine `PermissionRequest`, und wird durch `handle_permission_response()` aufgelöst, sobald die WinUI-Antwort eintrifft. `PermissionService.set_dialog_factory()` und `CommandTool.configure_remote_permissions()` erlauben das Austauschen der Standard-Dialog-Kette nach Konstruktion, ohne den Qt/Konsolen-Pfad für andere Launch-Modi zu verändern. WinUI zeigt einen neuen `PermissionDialog` mit Risiko-Badge und (bei HIGH) Pflicht-Eingabe der vom Backend gesendeten Sicherheitsphrase, bevor der Bestätigen-Button aktiviert wird.  
**Getestet:** 5 neue Unit-Tests (`tests/test_grpc_permission_bridge.py`) für Auflösung, Ablehnung, Timeout, unbekannte Request-ID, Sicherheitsphrase-Übertragung — ohne echte Netzwerkverbindung, direkt gegen die Bridge-Logik.  
**Phase:** 4

| Priorität | Anzahl | Behoben | Zielphase |
|---|---|---|---|
| Kritisch (Prio 1) | 5 | 5/5 ✅ | Phase 2–3 |
| Hoch (Prio 2) | 6 | 5/6 (TD-006, TD-007, TD-010, TD-017; TD-009 zurückgestellt) | Phase 2–5 |
| Mittel (Prio 3) | 6 | 0/6 | Phase 1–8 |
| Aus Security-/Bug-Gegencheck (TD-018 bis TD-024) | 7 | 6/7 (offen: TD-019) | Phase 1–3 |
| Phase-4-Funde (TD-025) | 1 | 1/1 ✅ | Phase 4 |
| **Gesamt** | **25** | **18/25** (+TD-009 begründet zurückgestellt) | |

**Verbleibend offen:** TD-008 (hardcoded deutsche Strings, erst Phase 7+ relevant), TD-011 (Designsystem-Inkonsistenz — größere Aufgabe, alte Token-Namen in einigen Seiten), TD-012 bis TD-016 (Mittel: Repo-Umbenennung, Log-Aggregation, Token-Count, requirements-dev.txt, Debug-Dateien im Root), TD-019 (SecretsVault-Locking, niedriges Risiko, nur relevant bei `encrypted_file`-Backend).
