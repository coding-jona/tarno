# TARNO Research and Decision Log

Version: 1.0 · Datum: 2026-07-10 · Status: Research & Architecture Phase

Dieses Dokument protokolliert jede Architekturentscheidung für TARNO, inklusive betrachteter Alternativen, Begründungen und offenen Fragen.

---

## D-01: Gesamtarchitektur — OpenVoiceOS als Basis vs. Eigenentwicklung

**Frage:** Soll TARNO auf der kompletten OpenVoiceOS-Distribution aufbauen oder nur einzelne Komponenten nutzen?

**Betrachtete Alternativen:**
- A: Komplette OVOS-Distribution (ovos-core + ovos-bus + ovos-listener + ovos-audio)
- B: Nur Voice-Komponenten aus OVOS (Plugin-Manager, Listener, Audio)
- C: Alles selbst bauen

**Entscheidung:** B mit erweitertem ovos-core als Brain

**Begründung:**
- `ovos-core` bietet bewährte Intent-Pipeline, Skill-System, Persona-Pipeline und Plugin-Architektur
- `ovos-persona` + Solver Plugins ermöglichen es, TARNO als AI-Agent mit eigenem Charakter zu definieren
- ovos-plugin-manager, ovos-listener und ovos-audio bieten die modulare Audio- und Voice-Infrastruktur
- Eigener TARNO-Persona/Solver-Plugin implementiert Mistral-Integration, Tool-Auswahl, Memory und Planung
- Der Nutzer wünscht sich bewusst, ovos-core als Brain zu kombinieren und das Beste aus der Community (z. B. OpenTarno, TARNO-MT67, JRVS) zu übernehmen

**Offene Fragen:**
- Windows-Kompatibilität von ovos-core, ovos-listener und ovos-audio prüfen
- Eventuelle Ersatzlösung für Microphone-Streaming unter Windows
- Wie genau die TARNO-Persona in `ovos-persona` konfiguriert wird

---

## D-02: Wake-Word-Technologie

**Frage:** Welche Wake-Word-Engine soll verwendet werden?

**Betrachtete Alternativen:**
- openWakeWord (lokal, ONNX, trainierbar)
- Porcupine (kommerziell, closed-source, kostenlos nur für private Projekte)
- Snowboy (eingestellt)
- Precise (Mycroft, wenig aktiv)
- OVOS Precise-Lite-Plugin

**Entscheidung:** openWakeWord

**Begründung:**
- Open Source, vollständig lokal, ONNX-basiert
- Bereits in TARNO vorhanden (`tarno/voice/wakeword.py`)
- Trainings-Notebooks und Community-Modelle verfügbar
- Geringe CPU-Last durch ONNX-Optimierung
- Als OVOS-Plugin verfügbar: `ovos-ww-plugin-openwakeword`

**Offene Fragen:**
- Eigenes "hey_tarno"-Modell trainieren oder vortrainiertes Modell verwenden?
- Integration in ovos-plugin-manager testen

---

## D-03: Speech-to-Text (STT)

**Frage:** Welche STT-Engine soll für Spracherkennung verwendet werden?

**Betrachtete Alternativen:**
- Google Speech API (online, einfach, aber nicht privat)
- OpenAI Whisper (offline, aber langsam auf CPU)
- faster-whisper (schneller, weniger RAM, CTranslate2)
- Vosk (leicht, aber geringere Genauigkeit im Deutschen)
- OVOS Whisper-Plugin

**Entscheidung:** faster-whisper

**Begründung:**
- Bis zu 4x schneller als OpenAI Whisper bei gleicher Genauigkeit
- Geringer RAM-Verbrauch durch `int8` Quantisierung
- CPU-optimiert (CTranslate2)
- VAD-Filter für bessere Echtzeitfähigkeit
- Offline-fähig
- Empfohlene Konfiguration: `base` oder `small` Modell, `device="cpu"`, `compute_type="int8"`, `language="de"`

**Offene Fragen:**
- Streaming-Transkription in Echtzeit umsetzen (whisper_streaming oder eigener Puffer)
- Modellgröße Balance zwischen Latenz und Genauigkeit finden

---

## D-04: Text-to-Speech (TTS)

**Frage:** Welche TTS-Engine soll verwendet werden?

**Betrachtete Alternativen:**
- gTTS (online, einfach, aber Latenz und Abhängigkeit)
- edge-tts (aktuell in TARNO, online, gute Qualität)
- Piper TTS (lokal, schnell, ONNX, CPU-only)
- Coqui TTS (lokal, gute Qualität, aber schwerer)
- OVOS Piper-Plugin

**Entscheidung:** Piper TTS

**Begründung:**
- Lokal, keine Internet-Abhängigkeit
- Sehr schnell, sogar auf Raspberry Pi 5
- ONNX-basiert, CPU-optimiert
- Mehrere Sprachen und Stimmen verfügbar
- Deutsches Modell `thorsten` verfügbar

**Offene Fragen:**
- Beste deutsche Stimme für TARNO auswählen
- Piper als `ovos-tts-plugin-piper` oder direkte Python-Integration
- `edge-tts` als Fallback während Migration beibehalten

---

## D-05: Audio Management / Microphone Pipeline

**Frage:** Wie soll die Audio-Pipeline zwischen Mikrofon, Wake-Word, VAD und STT aussehen?

**Betrachtete Alternativen:**
- Eigener `AudioStream` + `pyaudio` (aktuell in TARNO)
- `ovos-listener` + `ovos-microphone-plugin-pyaudio`
- `sounddevice` + eigener VAD-Loop
- `speech_recognition` Bibliothek (aktuell in TARNO, aber nicht optimiert)

**Entscheidung:** Zuerst `ovos-listener` evaluieren; Fallback auf eigenen `AudioStream` mit `sounddevice`/`pyaudio` und `webrtcvad`/`silero-vad`.

**Begründung:**
- ovos-listener bietet einheitliche Events und Plugin-Architektur
- Aktueller `AudioStream` basiert auf PyAudio, ist aber sehr einfach gehalten
- Windows-Kompatibilität ist ein Risiko für ovos-listener
- VAD (Voice Activity Detection) ist essenziell für gute Echtzeit-STT

**Offene Fragen:**
- Windows-Tests mit ovos-listener durchführen
- VAD-Engine auswählen (`webrtcvad` vs. `silero-vad` vs. VAD in faster-whisper)

---

## D-06: Event-System / Kommunikation zwischen Komponenten

**Frage:** Wie kommunizieren die Komponenten (Wake-Word, STT, TTS, Agent)?

**Betrachtete Alternativen:**
- Eigener `EventBus` (aktuell in `tarno/core/events.py`)
- `ovos-bus` (WebSocket-basiert)
- Qt-Signals (nur in GUI-Modus)
- Kombination aus internem EventBus + ovos-bus-client

**Entscheidung:** Eigener `EventBus` bleibt primär; `ovos-bus-client` als optionale Brücke für externe OVOS-Komponenten.

**Begründung:**
- Eigener EventBus ist bereits vorhanden und leichtgewichtig
- ovos-bus würde WebSocket-Overhead einführen
- Qt-Signals sind GUI-spezifisch und nicht für den Voice-Loop geeignet

**Offene Fragen:**
- Soll der EventBus thread-safe sein?
- Async-Integration für bessere Performance?

---

## D-07: LLM Provider Architektur

**Frage:** Soll TARNO nur Mistral oder mehrere Provider unterstützen?

**Betrachtete Alternativen:**
- A: Nur Mistral (einfacher, optimiert)
- B: Multi-Provider (Mistral, Claude, Gemini, Groq, Ollama, HuggingFace)

**Entscheidung:** B

**Begründung:**
- `LLMProvider`-Abstraktion existiert bereits
- Flexibilität, Redundanz, Ausfallsicherheit
- Nutzer kann lokalen Ollama-Modell verwenden oder Cloud-API
- Mistral bleibt primärer Default-Provider

**Offene Fragen:**
- Tool-Call-Format über alle Provider harmonisieren
- Kosten/Latenz-Optimierung für Mistral-API

---

## D-08: Memory System

**Frage:** Wie soll das Langzeitgedächtnis umgesetzt werden?

**Betrachtete Alternativen:**
- A: Nur Conversation-History (kurzzeitig)
- B: SQLite für Fakten + ChromaDB/FAISS für semantische Suche
- C: Vollwertige Vector-DB mit Embeddings
- D: Graph-Datenbank (z. B. Neo4j) für Beziehungen

**Entscheidung:** B

**Begründung:**
- SQLite ist für strukturierte Nutzerdaten und Einstellungen ausreichend
- ChromaDB/FAISS ermöglicht semantische Suche in Dokumenten und Konversationen
- Sentence Transformers für Embeddings (CPU-geeignet, Mehrsprachig)
- Graph-Datenbank ist overkill für aktuelle Anforderungen

**Offene Fragen:**
- Embedding-Modell auswählen (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`)
- Speicherstruktur für Konversationen, Fakten, Aufgaben definieren

---

## D-09: Tool-Execution-Layer

**Frage:** Wie werden Tools definiert, geladen und ausgeführt?

**Betrachtete Alternativen:**
- A: Einfache Python-Funktionen mit JSON-Schema (aktuell in `tarno/ai/tool_registry.py`)
- B: OVOS-Plugin-Manager für Tools
- C: Eigenes Plugin-System mit Discover-Funktion

**Entscheidung:** A + C

**Begründung:**
- Aktuelle `ToolRegistry` ist funktional und einfach
- TARNO-spezifische Tools (PC-Automation, Minecraft, etc.) benötigen spezifische Schnittstellen
- Erweiterung um dynamisches Laden aus `tarno/plugins/` und `~/.tarno/plugins/`

**Offene Fragen:**
- Tool-Permission-System implementieren
- Sandbox für gefährliche Tools (z. B. `execute_command`)

---

## D-10: Plugin-System für Voice-Komponenten

**Frage:** Sollen Wake-Word, STT, TTS und Microphone als austauschbare Plugins geladen werden?

**Betrachtete Alternativen:**
- A: Hartcodierte Klassen
- B: `ovos-plugin-manager` (OPM)
- C: Eigenes Plugin-Loader-System

**Entscheidung:** B für Voice-Komponenten, C für TARNO-Tools

**Begründung:**
- OPM standardisiert STT/TTS/Wake-Word/Microphone-Plugins
- Große Auswahl an existierenden Plugins
- TARNO-Tools sind spezifisch und benötigen eigene Definition

**Offene Fragen:**
- Entry-Points in `pyproject.toml` definieren
- Laufzeitkonfiguration über `tarno_config.yaml`

---

## D-11: GUI / Frontend

**Frage:** Soll parallel an GUI/Frontend gearbeitet werden?

**Betrachtete Alternativen:**
- A: Ja, PySide6-GUI weiterentwickeln
- B: Nein, Fokus auf Voice + AI Engine

**Entscheidung:** B

**Begründung:**
- Megaplan priorisiert Voice + AI Engine
- GUI/Frontend ist nicht Teil dieses Architektur-Milestones
- Bestehende GUI kann später wieder aufgegriffen werden

**Offene Fragen:**
- Späteres UI-Konzept (z. B. BuildMC-Design) separat planen

---

## D-12: Community Research — Beste TARNO-Projekte

**Frage:** Welche TARNO-Community-Projekte existieren und was macht sie erfolgreich?

**Betrachtete Projekte:**
- **OpenTarno:** CLI-first Agent mit Memory-Indexierung, Briefings, Multi-Provider
- **TARNO-MT67:** Echtzeit-Voice, Vision, Browser-Automation, Systemsteuerung, Multi-Step-Agent, Soul-System
- **JRVS:** Holografisches UI, Audio-Visualisierungen, Gaming-Automation

**Entscheidung:** Beste Features in TARNO-Roadmap übernehmen

**Begründung:**
- Community-Projekte zeigen, welche Features Nutzer tatsächlich wollen
- Kein Grund, diese Konzepte neu zu erfinden
- TARNO-MT67 ist technisch dem Iron-Man-Vorbild am nächsten

**Zu übernehmende Features:**
- Memory-Indexierung und semantische Suche
- Persönliche Briefings
- Vision (Screenshot + Kamera)
- Browser-Automation (Playwright)
- Systemsteuerung per Sprache
- Multi-Step-Agent
- Langfristiges Memory
- Persönlichkeit / Soul System

---

## D-13: Iron Man TARNO Feature Map

**Frage:** Welche Fähigkeiten des filmischen TARNO sind realistisch umsetzbar und in welcher Priorität?

**Entscheidung:** Realistische Roadmap mit P0-P3-Prioritäten

| Priorität | Fähigkeit | Beschreibung | Phase |
|-----------|-----------|--------------|-------|
| P0 | Always-on Wake Word | "Hey TARNO" aktiviert den Agenten | 2 |
| P0 | Natürliche Sprachausgabe | Lokal, schnell, Charakterstimme | 2 |
| P0 | Dialog + Tool-Aufrufe | Sprachbefehle → Aktionen | 3 |
| P1 | Langfristiges Memory | Nutzer lernt, Präferenzen, Fakten | 4 |
| P1 | Systemsteuerung | Apps, Lautstärke, Helligkeit, Prozesse | 4 |
| P1 | Browser-Automation | Suchen, Tabs, Formulare, Playwright | 5 |
| P2 | Screenshot / Bildschirmanalyse | Visuelles Verständnis des Desktops | 5 |
| P2 | Webcam-Vision | Kamera-Input analysieren | 5 |
| P2 | Multi-Step-Agent | Komplexe Aufgaben in Schritten lösen | 5 |

**Ausgeklammert (P3 / später):** Proaktive Briefings, holografisches UI, HUD-Overlay.

**Begründung:**
- 1:1-Klon des filmischen TARNO ist aktuell unmöglich (z. B. echte AGI, holografische Projektion)
- Nutzer bestätigt: Fokus auf P0–P2 für die nächsten Monate
- Priorität P0/P1 bilden die Basis für einen nützlichen, natürlichen Agenten

---

## Offene Entscheidungen

| ID | Thema | Beschreibung | Blockiert |
|----|-------|--------------|-----------|
| O-01 | Windows-Kompatibilität ovos-core | Testen, ob ovos-core und ovos-listener unter Windows laufen | Phase 1 |
| O-02 | Piper-Stimme | Deutsches Stimmmodell auswählen | Phase 2 |
| O-03 | VAD-Engine | `webrtcvad`, `silero-vad` oder faster-whisper VAD | Phase 2 |
| O-04 | Embedding-Modell | Mehrsprachiges Modell für Memory | Phase 4 |
| O-05 | Tool-Sandbox | Sichere Ausführung von `execute_command` | Phase 4 |
| O-06 | TARNO-Persönlichkeit | System-Prompts / Soul-System / Persona-JSON | Phase 3 |

---

## Akzeptanzkriterien für Architektur-Review

- [ ] Alle Voice-Komponenten sind als Plugins oder Module definiert
- [ ] LLM-Provider-Abstraktion unterstützt Mistral + Fallbacks
- [ ] Tool-System erlaubt sichere, erweiterbare Aktionen
- [ ] Memory-System-Konzept steht (SQLite + Vector DB)
- [ ] Keine GUI-Abhängigkeit im Voice-Loop
- [ ] Windows- und Linux-Kompatibilität berücksichtigt
- [ ] API-Keys und sensible Konfiguration sind externalisiert
