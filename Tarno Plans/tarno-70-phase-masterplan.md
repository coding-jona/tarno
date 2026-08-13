# TARNO: Der 70-Phasen-Masterplan zur Vollautonomie

Ursprünglich als 60-Phasen-Plan konzipiert; um Block 7 (Vision-Layer, Phasen 61-70)
erweitert, nachdem der Nutzer entschieden hat, TARNO eine permanente Kamera zu geben.

Status: Block 1 (Phasen 1-10) ist implementiert und verifiziert (siehe
`tarno/voice/adaptive_listener.py`, `tarno/core/config.py` VADConfig). Blöcke 2-7
sind geplant, noch nicht implementiert.

## Block 1: Audio-Inbound, Robustes VAD & TTS-Output (Phasen 1–10) — ERLEDIGT

Ziel: Die Kommunikation flüssig machen, das Abschneiden beim Sprechen killen und die
Grundlage für autonome Sprachausgabe schaffen.

* Phase 1: Implementierung des PyAudio-Eingangs-Streams mit lokalem Ringpuffer und
  grundlegender digitaler Rauschunterdrückung.
* Phase 2: Integration des Wake-Word-Daemons für "Hey Jarvis" / "Hey Tarno" (lokal
  via OpenWakeWord oder pvporcupine — tatsächlich implementierte Backends, siehe
  `tarno/voice/wakeword.py`, `WakeWordDetector`).
* Phase 3: Einbau einer energie-basierten VAD (RMS-Schwellenwert mit
  Noise-Floor-Kalibrierung) für präzise Erkennung von Sprache vs. Hintergrundgeräuschen
  — implementiert in `AdaptiveListener` (`tarno/voice/adaptive_listener.py`), kein
  `webrtcvad`-Package im Projekt.
* Phase 4: Dynamic Silence Timeout: Anhebung des Stille-Schwellenwerts auf ein
  konfigurierbares Fenster von 1,5 bis 2,0 Sekunden.
* Phase 5: Trailing-Punctuation-Schleife: Integration eines extrem leichten lokalen
  Modells, das prüft, ob der transkribierte Satz semantisch auf unvollständigen
  Konjunktionen oder Füllwörtern ("und", "äh", "weil") endet.
* Phase 6: Dynamische Erweiterung des Aufnahme-Fensters um weitere 2,0 Sekunden,
  falls die Trailing-Punctuation-Schleife anschlägt.
* Phase 7: Entwicklung des asynchronen Speech-Dispatcher-Threads für den
  Audio-Output (Text-to-Speech via Edge-TTS oder lokalem Piper).
* Phase 8: Entkopplung der TTS-Engine vom Input-Loop, damit Tarno sich ohne
  vorherigen Nutzer-Trigger eigenständig über die Lautsprecher zu Wort melden kann.
* Phase 9: Implementierung einer Audio-Ducking-Logik: Wenn Tarno von sich aus
  spricht, wird eventuell laufender PC-Sound temporär leiser geregelt.
* Phase 10: Zusammenfassung des Audio-Layers in einem sauberen, modular testbaren
  Python-Skript inklusive einer `config.json` für alle Timeouts.

## Block 2: Der dreischichtige Risiko-Router & PC-Zugriff (Phasen 11–20)

Ziel: Beseitigung aller nervigen Falsch-Positives bei banalen Befehlen wie der
Uhrzeit. Einrichtung des entspannten Risikomodells.

**Hinweis:** Grundgerüst existiert bereits in `tarno/core/command_engine.py`
(`class RiskLevel(Enum)`, `def assess_risk(...)`). Phasen 11-20 bauen darauf auf/
erweitern, nicht bei null neu implementieren.

* Phase 11: Implementierung des lexikalischen Vorfilters mittels regulärer
  Ausdrücke (Regex) zur Abwehr trivialer Prompt-Injections (<1 ms Latenz).
* Phase 12: Integration des strukturellen Filters zur strikten Trennung von
  vertrauenswürdigem Systemkontext und Benutzerdaten (Input Spotlighting).
* Phase 13: Bau der Exekutiven Routing-Komponente (Kognitiv-Exekutive Separation):
  Das LLM generiert nur deklarative JSON-Befehle, führt sie aber niemals selbst aus.
* Phase 14: Klassifizierung Stufe 3 (Niedriges Risiko): Whitelist für rein
  informative Abfragen (`get_time`, `get_weather`, `read_calendar`) — vollautonom
  ohne Benutzerinteraktion.
* Phase 15: Anbindung der Windows-API via `pywin32` und `pygetwindow` zur Erfassung
  aktiver Desktop-Fenster, Prozesstitel und Ausführungszeiten.
* Phase 16: Klassifizierung Stufe 2 (Mittleres Risiko): OS-Interaktionen
  (`close_window`, `focus_application`, `change_volume`, `start_program`).
* Phase 17: Autonome Abwägungs-Logik für Stufe 2: Tarno entscheidet selbstständig
  über die Ausführung, meldet die Aktion aber zeitgleich über den Speech-Dispatcher.
* Phase 18: Klassifizierung Stufe 1 (Hohes Risiko): harte Systemgrenzen
  (`delete_file`, `format_drive`, `shutdown_pc`).
* Phase 19: Hochrisiko-Sicherheitsphrasen-Bestätigung: Bei Stufe-1-Aktionen friert
  die Pipeline ein und verlangt zwingend manuelle Passphrasen-Eingabe
  (Human-in-the-Loop).
* Phase 20: Umfassender Testlauf der Risiko-Pipeline (Uhrzeit-Abfrage triggert nie
  wieder eine Sicherheitswarnung).

## Block 3: Autonome Trigger-Engine & Der echte Jarvis-Eigenwille (Phasen 21–30)

Ziel: Tarno das selbstständige Agieren und Reagieren beibringen.

* Phase 21: Permanenter Background-Daemon-Loop, unabhängig von Benutzer-Prompts im
  10-Sekunden-Takt.
* Phase 22: Zeit- & Termin-Observer: Kontinuierlicher Abgleich lokaler Kalenderdaten.
* Phase 23: System- & Netzwerk-Observer: Server-Port-Erreichbarkeiten,
  Docker-Container, kritische Systemauslastung via `psutil`.
* Phase 24: User-Behavior-Observer: Inaktivität, exzessive Verweildauer in
  ablenkenden Anwendungen während anstehender Termine.
* Phase 25: Proaktiver Gedanken-Slot im LLM-Kontext: eigenständige
  "Handlungsentwürfe" im Hintergrund.
* Phase 26: Relevanz-Filter (TRACES-Prinzip): Jeder autonome Handlungsentwurf wird
  von einem Mikro-Klassifikator mit Score (0–100) bewertet.
* Phase 27: Schwellenwert (Score > 85): Nur bei extrem hoher Relevanz wird die
  TTS-Ausgabe getriggert.
* Phase 28: "Anti-Ablenkungs-Exekutive": Bei kritischem Termin, ausbleibender
  Reaktion und triggerndem Score schließt Tarno das ablenkende Fenster autonom.
* Phase 29: "Iterative Neugier": Tarno scannt bei Systemleerlauf offene Tasks und
  bittet bei semantischen Lücken selbstständig um Vervollständigung.
* Phase 30: Stresstest des autonomen Loops zur Vermeidung von endlosen
  Sprachausgabe-Schleifen.

## Block 4: Kontextuelles Gedächtnis & Memory-Layer (Phasen 31–40)

* Phase 31: Lokale Vektordatenbank (ChromaDB/Qdrant) für semantisches
  Langzeitgedächtnis.
* Phase 32: Automatischer Memory-Extractor nach jedem Gespräch.
* Phase 33: Dynamischer Kontext-Abrufs (RAG) bei jeder Eingabe/jedem Trigger.
* Phase 34: Bekämpfung von Persona-Drift via Constitutional-AI-Instruktionen.
* Phase 35: Relevanz-Erosion (Memory Pruning) für veraltete/einmalige Informationen.
* Phase 36: Synchronisation Memory-Layer ↔ autonome Trigger-Engine.
* Phase 37: Lokale JSON-Schnittstelle zur manuellen Einsicht/Korrektur.
* Phase 38: Optimierung der Einbettungs-Latenz (lokales ONNX-Modell, Sub-10ms).
* Phase 39: Kurzzeitgedächtnis-Puffer (letzte 10 Interaktionen).
* Phase 40: Validierung bei komplexen, verschachtelten Nutzerfragen.

## Block 5: Isolierte Exekutiv-Sandbox & Agentic Safeties (Phasen 41–50)

**Hinweis:** Mehrere Phasen überlappen mit bereits existierendem Code aus der
Security-Härtungs-Session — dort erweitern statt neu bauen:
- Phase 43/49 (Trajektorien-Überwachung/Rate-Limiting): teilweise vorhanden in
  `tarno/security/content_filter.py` (`is_input_safe`/`is_output_safe`) und
  `tarno/core/executor.py` (`_rate_limit_exceeded`, `_MAX_EXECUTIONS_PER_WINDOW`).
- Phase 47 (Verschlüsselung API-Keys): vollständig vorhanden in
  `tarno/security/secrets.py` (Keyring + Fernet-Backend).
- Phase 48 (fälschungssicheres Audit-Log): vollständig vorhanden in
  `tarno/security/audit.py` (`AuditManager.verify_integrity()`,
  `AuditManager.rotate_old_logs()`), bereits in `engine.py` verdrahtet.

* Phase 41: Isolierte Ausführungsumgebung (Sandbox/Wrapper) für Systemaufrufe.
* Phase 42: Harte Typprüfung für LLM-generierte JSON-Aktions-Argumente.
* Phase 43: Proaktive Trajektorien-Überwachung (TS-Guard/TS-Flow) gegen schädliche
  Befehlsketten.
* Phase 44: Härtung gegen Excessive Agency (Argumenten-Längen-Limits).
* Phase 45: Automatischer Rollback-Mechanismus bei fehlgeschlagener Stufe-2-Aktion.
* Phase 46: Physischer Kill-Switch (globaler Hotkey, z.B. `Strg+Alt+K`).
* Phase 47: Verschlüsselung sensibler API-Keys/Zugangsdaten (Keyring/Fernet).
* Phase 48: Fälschungssichere `tarno_executive.log` (Timestamp, Risikostufe,
  Ergebnis).
* Phase 49: Rate-Limiting für autonome Werkzeugaufrufe.
* Phase 50: Adversarialer Stresstest gegen geschützte Systemdatei-Manipulation.

## Block 6: UI/UX-Synthese, Front-End-Anbindung & Live-Betrieb (Phasen 51–60)

* Phase 51: WebSocket/REST-Verbindung Python-Backend ↔ TARNO-Frontend.
* Phase 52: Visuelle Pop-ups synchron zur autonomen Sprachausgabe (Glow-Effekt).
* Phase 53: Echtzeit-Statusanzeige im GUI ("Denkt nach...", "Hört zu...", ...).
* Phase 54: Visualisierung Memory-Layer + aktive Tasks in der Sidebar.
* Phase 55: GUI-Schalter für Autonomie-Stufe (1/2/3) im laufenden Betrieb.
* Phase 56: Output-Guardrails vor TTS-Ausgabe (Halluzinationen/Code-Fragmente).
* Phase 57: Performance-Optimierung der GUI-Renderknoten.
* Phase 58: Latenz-Optimierung Audio → Vektor-Suche → LLM → TTS.
* Phase 59: 24h-Langzeit-Stresstest (Memory-Leaks).
* Phase 60: Finaler Live-Going-Meilenstein.

## Block 7: Vision-Layer — Permanente Kamera & autonome Bildreaktion (Phasen 61–70)

Ziel: TARNO bekommt "Augen" — eine permanent aktive Kamera, die selbstständig
erkennt, wann sich relevant etwas im Sichtfeld geändert hat, und darauf reagiert.
Fügt sich als vierter Observer neben Zeit/System/User-Behavior in die autonome
Trigger-Engine (Block 3) ein und läuft durch denselben TRACES-Relevanz-Filter
(Phase 26), bevor Tarno tatsächlich reagiert.

**Recherche-Grundlage (2026-07-19):** OpenAI (GPT-4o Vision) sampled Frames mit
2-4 fps während erkannter Bewegung, deutlich weniger bei Stillstand, und skaliert
sie vor dem Modellaufruf auf ~512-720px herunter — mechanische Vorfilterung lokal,
die eigentliche Bewertung "was ist wichtig" übernimmt danach das Modell. Googles
Project Astra (Gemini Live) hält die interne Frame-Selection-Architektur nicht
öffentlich dokumentiert; bekannt ist nur das Nutzererlebnis (simultane
Video+Audio-Verarbeitung, niedrige Latenz, Objekt-Gedächtnis). TARNOs Ansatz folgt
dem einzigen öffentlich bestätigten Muster (variable Sampling-Rate + Downscaling),
mit stärkerem Gewicht auf der lokalen Kostenbremse, da TARNO dauerhaft im
Hintergrund läuft statt nur während eines aktiven Voice-Calls.

* Phase 61: Kamera-Capture-Modul (OpenCV, `cv2.VideoCapture`), konfigurierbare
  Basis-FPS, läuft permanent und rein lokal (kein Frame verlässt ohne Trigger den
  Rechner).
* Phase 62: Lokales Motion-Gate (Frame-Diff/SSIM) als reine Kostenbremse — prüft
  nur "hat sich überhaupt etwas bewegt", trifft keine Relevanz-Entscheidung.
* Phase 63: Kandidaten-Frame-Sammlung: bei erkannter Bewegung mehrere Frames aus
  dem Bewegungsfenster sammeln statt nur eines.
* Phase 64: Preprocessing/Downscaling (Ziel ~512-720px längste Kante) vor jedem
  Modellaufruf zur Kosten-/Latenzreduktion.
* Phase 65: Integration von `pixtral-large-latest` als eigener Vision-Provider-Pfad
  (separat vom bestehenden Text-Tiering in `MistralConfig.difficulty_tiers`, da
  aktuell konfigurierte Modelle keinen Bild-Input unterstützen).
* Phase 66: Frame-Selection-Prompt: Pixtral wählt selbst das relevanteste Frame aus
  den Kandidaten und bewertet, ob überhaupt eine Reaktion angebracht ist — die
  "was ist wichtig"-Entscheidung liegt bei der KI, nicht bei Code-Heuristiken.
* Phase 67: Vision-Observer als vierter Observer in die autonome Trigger-Engine
  (Block 3, `_run_loop`-Äquivalent) einhängen.
* Phase 68: TRACES-Relevanz-Score-Integration: Vision-Events durchlaufen denselben
  0-100-Score-Mikro-Klassifikator (Phase 26) wie die übrigen Observer, bevor eine
  TTS-Ausgabe getriggert wird.
* Phase 69: Privacy-/Sicherheits-Layer: sichtbarer Kamera-Status-Indikator (GUI +
  ggf. Hardware-LED-Respekt), Recording-Opt-out, keine Cloud-Persistenz einzelner
  Frames über den Analyse-Call hinaus.
* Phase 70: Kalibrierung/Stresstest: Sampling-Rate und Motion-Threshold
  feinjustieren, End-to-End-Latenz zwischen Trigger und gesprochener Reaktion
  messen.

## Ausblick: Google Calendar / Google Workspace-Integration (separater Plan)

Idee (2026-07-19): TARNO mit Google Calendar und Google Workspace verbinden, damit
TARNOs verwaltete Termine und die eigenen Termine des Nutzers gemeinsam einsehbar
sind — auch unterwegs (mobil, außerhalb des Windows-PCs). Bewusst **nicht** Teil
dieses 70-Phasen-Plans (Bezug primär zu Desktop-Autonomie); wird bei Bedarf als
eigener, separater Plan ausgearbeitet (Google Calendar API, OAuth-Flow,
Sync-Strategie TARNO ↔ Nutzer-Termine, Mobile-Zugriff).
