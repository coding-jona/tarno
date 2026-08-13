# TARNO AI Voice Assistant — Professional Engineering Specification & SWE Agent Instructions

Version: 1.0 · Project Type: Personal AI Agent Platform · Development Role: Principal AI Engineer / Software Architect

This document is a professional engineering specification for a modular, CPU-first, open-source-backed personal AI voice assistant that integrates **OpenVoiceOS as the agent brain** (via `ovos-core` + Personas/Solver Plugins), `openWakeWord`, `faster-whisper`, `Piper TTS`, Mistral AI, and a TARNO-specific persona layer. The aspirational goal is a real-world implementation as close as possible to Tony Stark's J.A.R.V.I.S. from the Iron Man universe.

---

# 0. Executive Mission

Du übernimmst die Rolle eines Principal Software Engineers, AI-System-Architekten und Voice-Assistant-Spezialisten.

Deine Aufgabe ist die Entwicklung einer professionellen KI-Assistenten-Plattform mit dem Namen **TARNO**. Das Ziel ist kein klassischer Smart-Speaker-Sprachassistent, sondern ein **Tony-Stark-ähnlicher persönlicher KI-Agent**, der:

- Dauerhaft über Wake-Word erreichbar ist
- Natürlich spricht und zuhört
- Den Kontext des Nutzers über Sitzungen hinweg behält
- Langfristiges Gedächtnis hat (Präferenzen, Fakten, Aufgaben)
- Tools und Systemfunktionen über Sprache steuert
- Den Browser und das Dateisystem bedienen kann
- Screenshots, Webcam und Bildschirminhalt auswerten kann
- Autonom komplexe Aufgaben in mehreren Schritten löst
- Eine ausgeprägte Persönlichkeit hat (trockener Humor, loyal, proaktiv)
- Erweiterbar ist durch Plugins und neue Fähigkeiten

Die Plattform soll langfristig mit modernen Sprachassistenten und den besten Community-Implementierungen von TARNO konkurrieren können.

---

# 1. Wichtigste Regel

**Baue NICHT alles von Grund auf neu.**

Vor der Implementierung MUSST du bestehende Open-Source-Projekte analysieren und passende Komponenten auswählen. Nur notwendige Teile werden integriert; das **TARNO-Gefühl und die eigene Persönlichkeitsschicht** werden selbst entwickelt.

OpenVoiceOS dient als **technische Basis und Brain**:

- `ovos-core` für Intent-Pipeline, Skill-System und Persona-Routing
- `ovos-persona` + Solver Plugins für LLM-Integration und Agenten-Verhalten
- `ovos-plugin-manager` für Voice-Plugins (STT, TTS, Wake-Word, Microphone)
- `ovos-bus` für Kommunikation zwischen Komponenten
- `ovos-listener` für Audio-Pipeline

---

# 2. Zielarchitektur

## Layer 1: Wake Word

- **Aufgabe:** Dauerhafte Überwachung auf „Hey TARNO“.
- **Technologie:** `openWakeWord`
- **Eigenschaften:** lokal, schnell, CPU-effizient, geringe Hintergrundlast
- **Integration:** `ovos-ww-plugin-openwakeword` via `ovos-plugin-manager`

## Layer 2: Audio Management

- **Aufgabe:** Mikrofonverwaltung, Audioaufnahme, Audio-Events, Streaming
- **Technologie:** `ovos-listener` + `ovos-microphone-plugin-pyaudio` (oder `sounddevice` auf Windows)
- **Alternative:** Eigener AudioStream basierend auf PyAudio/sounddevice, falls ovos-listener zu schwer für Windows ist

## Layer 3: Speech Recognition

- **Aufgabe:** Sprache → Text
- **Technologie:** `faster-whisper`
- **Anforderungen:** CPU-kompatibel, geringe Latenz, gute Erkennung
- **Empfohlene Konfiguration:**
  - Modell: `base` oder `small` für schnelle Reaktion, `medium` für bessere Genauigkeit
  - `device="cpu"`, `compute_type="int8"`
  - VAD-Filter aktiv (`vad_filter=True`)
  - `language="de"` (oder automatische Erkennung)

## Layer 4: Agent Brain — OpenVoiceOS Core

- **Wichtigster Teil:** `ovos-core` als Brain und Intent-Pipeline
- **TARNO-Persönlichkeit:** Eigene `TARNO`-Persona über `ovos-persona` / Persona Pipeline
- **Aufgaben:**
  - Intent-Pipeline und Skill-Routing
  - Persona-basierte Konversation
  - Solver-Plugin-Chain (LLM, Suche, Wissen, Tools)
  - Routing an TARNO-spezifische Tools und Skills

## Layer 5: TARNO Personality / Agent Core

- **Verantwortung:** TARNO-spezifische Persönlichkeit, Kontext, Memory, Tool-Auswahl, Planung
- **Technologie:** Eigener TARNO-Agent-Core, der als `ovos-solver-plugin` oder Skill an `ovos-core` angebunden wird
- **Primärer LLM:** Mistral AI API (`mistral-small-latest` / `mistral-medium-latest`)
- **Sekundär:** Claude, Gemini, Groq, Ollama, HuggingFace (Multi-Provider-Architektur beibehalten)
- **Wichtig:** Das Modell erhält **niemals** direkte Systemrechte. Alle Aktionen laufen über kontrollierte Tools.

## Layer 6: Tool Execution Layer

Alle Aktionen laufen über kontrollierte Tools. Beispiele:

- `open_application(app_name)`
- `analyze_file(filepath)`
- `read_log()`
- `execute_command(command, approved=False)`
- `manage_minecraft_server(action)`
- `system_information()`
- `web_search(query)`
- `take_screenshot()`

## Layer 7: Memory System

TARNO benötigt mehrere Speicherarten:

- **Kurzzeit:** aktueller Dialog (ConversationManager)
- **Langzeit:** Nutzerpräferenzen, bekannte Systeme, vergangene Aufgaben
- **Technologien evaluieren:**
  - SQLite für strukturierte Daten
  - ChromaDB / FAISS als Vector Database
  - Sentence Transformers für Embeddings

## Layer 8: Text-to-Speech

- **Technologie:** `Piper TTS`
- **Ziel:** schnell, lokal, dauerhaft verfügbar
- **Fallback:** `edge-tts` (aktuell) oder `gTTS`
- **Empfohlene Konfiguration:**
  - Modell: `de_DE-thorsten_medium` (oder vergleichbar)
  - CPU-only, ONNX Runtime

---

# 3. Hardware-Anforderungen

CPU-first:

- Keine Abhängigkeit von CUDA, ROCm oder GPU-Inferenz
- Geringe RAM-Nutzung
- Niedrige CPU-Last im Idle
- Schnelle Aktivierung

Empfohlene Mindestanforderungen:

- CPU: 4 Kerne (8 empfohlen)
- RAM: 8 GB (16 GB empfohlen)
- Festplatte: 2 GB für Modelle + Logs
- Mikrofon + Lautsprecher

---

# 4. OpenVoiceOS Research Auftrag

## ovos-core

- **URL:** https://github.com/OpenVoiceOS/ovos-core
- **Bewertung:** Zentrale NLP-, Skill- und Intent-Pipeline-Engine. Enthält das "Brain" von OpenVoiceOS: Skill-Service, Intent-Pipelines, CommonQuery, Converse-Framework, Persona-Pipeline.
- **Entscheidung:** **Einbinden als TARNO-Brain**. TARNO wird als eigene Persona über `ovos-persona` und als Solver-Plugin-Chain realisiert. `ovos-core` übernimmt das Routing, die Skill-Verwaltung und die Pipeline-Architektur.

## ovos-bus

- **URL:** https://github.com/OpenVoiceOS/ovos-bus
- **Bewertung:** Event-System über WebSocket. Erlaubt lose Kopplung zwischen Voice-, Audio- und Agent-Komponenten.
- **Entscheidung:** **Einbinden** als primäres Kommunikationssystem zwischen `ovos-core`, `ovos-listener`, `ovos-audio`, TTS, STT und TARNO-Tools.

## ovos-plugin-manager

- **URL:** https://github.com/OpenVoiceOS/ovos-plugin-manager
- **Bewertung:** Standardisiert Plugin-Interfaces für STT, TTS, Wake-Word, Microphone. Ermöglicht austauschbare Voice-Komponenten.
- **Entscheidung:** **Einbinden**, um Wake-Word, STT, TTS und Microphone als Plugins zu laden.

## ovos-listener

- **URL:** https://github.com/OpenVoiceOS/ovos-listener
- **Bewertung:** Metapackage für Speech Service. Verbindet Mikrofon, Wake-Word, VAD und STT.
- **Entscheidung:** Evaluieren, ob direkte Integration möglich ist. Bei Windows-Problemen eigenen Listener auf Basis von PyAudio/sounddevice + VAD bauen.

## ovos-audio

- **URL:** https://github.com/OpenVoiceOS/ovos-audio
- **Bewertung:** Audio-Output-Daemon mit TTS-Plugin-System.
- **Entscheidung:** TTS über `ovos-plugin-manager` und Piper-TTS-Plugin laden; eigene Ausgabeschicht beibehalten.

## openWakeWord

- **URL:** https://github.com/dscripka/openWakeWord
- **Bewertung:** Lokal, ONNX-basiert, trainierbare Wake-Word-Modelle.
- **Entscheidung:** **Einbinden** als `ovos-ww-plugin-openwakeword` oder direkt über `openwakeword.model`.
- **Training:** Eigene Modelle über Colab-Notebook oder `openwakeword` Training-Skripte möglich.

## faster-whisper

- **URL:** https://github.com/SYSTRAN/faster-whisper
- **Bewertung:** 4x schneller als OpenAI-Whisper, weniger RAM, CPU-optimiert via CTranslate2.
- **Entscheidung:** **Einbinden** als primäre STT-Engine über `ovos-stt-plugin-fasterwhisper` (falls verfügbar) oder eigener STT-Plugin.

## Piper TTS

- **URL:** https://github.com/rhasspy/piper
- **Bewertung:** Schnellste offline neuronale TTS, Raspberry Pi 5 tauglich, CPU-only.
- **Entscheidung:** **Einbinden** als `ovos-tts-plugin-piper` oder direkte Python-Integration.

---

# 4.1. Community Research — Beste TARNO-Projekte

## OpenTarno

- **URL:** https://github.com/open-tarno/OpenTarno
- **Highlights:**
  - CLI-first Agent mit `tarno ask`, `tarno memory`, `tarno digest`
  - Multi-Provider-LLM-Unterstützung
  - Persönliche Briefings (morning digest)
  - Memory-Indexierung und semantische Suche
- **Was TARNO übernehmen sollte:**
  - Konsistente CLI/Chat-Schnittstelle
  - Memory-Indexierung (`tarno memory index ./docs/`)
  - Persönliche Briefings und Zusammenfassungen

## TARNO-MT67

- **URL:** https://github.com/subhansh-dev/Tarno-MT67
- **Highlights:**
  - Echtzeit-Voice-Streaming mit Gemini 2.5 Flash Native Audio
  - Clap Detection als Wake-Trigger
  - Kamera- und Bildschirm-Vision (OpenCV + Gemini)
  - Browser-Automation (Playwright)
  - Systemsteuerung (Lautstärke, Helligkeit, Prozesse)
  - Telegram-Bridge
  - Multi-Step Agent
  - Langfristiges Memory
- **Was TARNO übernehmen sollte:**
  - Vision (Kamera + Screenshot)
  - Browser-Automation
  - Systemsteuerung per Sprache
  - Multi-Step-Agent-Planung
  - Langfristiges Memory
  - „Soul System“ (Persönlichkeit in Markdown)

## JRVS (lookitsjarv.us)

- **URL:** https://lookitsjarv.us/
- **Highlights:**
  - Holografische Electron-Overlay-UI im Iron-Man-Style
  - Real-time Audio-Visualisierungen
  - Gaming-Automation (AFK-Makros, OBS-Integration)
  - Always-on-Top Overlay
- **Was TARNO übernehmen sollte:**
  - Holografisches UI-Konzept für spätere GUI-Phase
  - Audio-Visualisierungen
  - Gaming-Integrationen

## Zusammenfassung: Community-Erfolgsfaktoren

- **Always-on Voice:** Wake-Word + Streaming-STT + TTS
- **Persönlichkeit:** System-Prompts, „Soul“, Charakterzüge
- **Vision:** Kamera, Screenshot, Bildschirmanalyse
- **Action:** Browser, Dateisystem, System, Apps, Makros
- **Memory:** Kurz- und Langzeitgedächtnis
- **Multi-Step:** Planen → Ausführen → Validieren → Berichten

---

# 5. Iron Man TARNO Feature Map

Das Ziel ist kein 1:1-Klon (das wäre aktuell unmöglich), sondern eine **realistische Roadmap für die nächsten Monate** (P0–P2):

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

---

# 6. Was NICHT gemacht werden soll

- Keine komplette OpenVoiceOS-Distribution
- Keine Smart-Home-Funktionen
- Keine unnötigen Skills
- Keine GUI / Frontend / Launcher Design (für diesen Megaplan ausgeklammert)

Fokus:

**VOICE + AI ENGINE**

---

# 7. Entwicklungsphasen

## Phase 0: Research

- Ergebnis: Dieses Dokument + `TARNO_RESEARCH_AND_DECISION_LOG.md`
- Enthält: Technologieentscheidungen, Alternativen, Begründungen
- Noch kein Code

## Phase 1: Foundation

- Repository-Struktur anpassen
- Dependency Management (`pyproject.toml` oder `requirements.txt`)
- Logging
- Configuration
- EventBus / MessageBus
- Plugin-Manager-Integration

## Phase 2: Voice Pipeline

Ziel: `Hey TARNO` → Audio → Text → Antwort

- Microphone-Plugin
- Wake-Word-Plugin (openWakeWord)
- VAD
- STT-Plugin (faster-whisper)
- TTS-Plugin (Piper)

## Phase 3: Mistral Integration

- API-Client
- Context Management
- Prompt System
- Multi-Provider-Abstraktion

## Phase 4: Agent Framework

- Tool System
- Permissions
- Memory (SQLite + Vector DB)
- Planning / Reasoning Loop

## Phase 5: Advanced Capabilities

- PC Automation
- Code-Analyse
- Minecraft-Integration
- Dokumenten-Analyse
- Browser-Automation

---

# 8. Engineering Standards

- Code: sauber, modular, dokumentiert, testbar
- Keine Hardcoded Keys (API-Keys über Env / Config)
- Keine riesigen Dateien (> 500 Zeilen aufteilen)
- Keine unstrukturierten Skripte
- Typisierung mit `from __future__ import annotations`
- Logging statt `print`
- Dependency Injection für Provider, Tools, Memory

---

# 9. Entscheidungsprinzip

Wenn mehrere Möglichkeiten existieren, bewerte:

1. Performance
2. Wartbarkeit
3. Erweiterbarkeit
4. Sicherheit
5. Zukunftsfähigkeit

Nicht die schnellste Lösung wählen. Die professionellste Lösung wählen.

---

# 10. Erste Aufgabe

Beginne NICHT mit Implementierung.

Führe zuerst aus:

1. Repository-Analyse (bestehende TARNO-Struktur)
2. OpenVoiceOS-Komponenten-Analyse
3. Architektur-Vorschlag
4. Entwicklungsplan

Erst nach Freigabe mit Code beginnen.

---

# 11. Research and Decision Log

## R-01: Wake-Word-Technologie

- **Optionen:** Porcupine, Precise, openWakeWord, Snowboy
- **Entscheidung:** openWakeWord
- **Begründung:** Open Source, trainierbar, ONNX-basiert, CPU-effizient, bereits in TARNO vorhanden, gute OVOS-Integration.

## R-02: Speech-to-Text

- **Optionen:** Google Speech API, OpenAI Whisper, faster-whisper, vosk
- **Entscheidung:** faster-whisper
- **Begründung:** 4x schneller als OpenAI Whisper, geringerer RAM-Verbrauch, CPU-optimiert, VAD-Filter, offline-fähig.

## R-03: Text-to-Speech

- **Optionen:** gTTS, edge-tts, Piper TTS, Coqui TTS
- **Entscheidung:** Piper TTS
- **Begründung:** Lokal, schnell, CPU-only, menschliche Stimme, keine Internet-Abhängigkeit. `edge-tts` bleibt als Fallback bis Piper integriert ist.

## R-04: Audio Management

- **Optionen:** Eigener PyAudio-Stream, ovos-listener, sounddevice
- **Entscheidung:** Zuerst `ovos-listener` + `ovos-microphone-plugin-pyaudio` evaluieren; bei Windows-Problemen eigener Listener auf PyAudio/sounddevice-Basis.
- **Begründung:** ovos-listener bietet einheitliche Events und Plugin-Architektur; Windows-Kompatibilität muss verifiziert werden.

## R-05: Event System

- **Optionen:** Eigener EventBus, ovos-bus, Qt-Signals
- **Entscheidung:** `ovos-bus` als primäres Event-System; eigener EventBus nur als interne Hilfsschicht für Komponenten, die noch nicht mit ovos-bus verbunden sind.
- **Begründung:** Da `ovos-core` als Brain verwendet wird, ist `ovos-bus` das natürliche Kommunikationssystem. Es ermöglicht lose Kopplung, externe Erweiterungen und spätere HiveMind-Integration.

## R-06: LLM Provider

- **Optionen:** Mistral-only, Multi-Provider
- **Entscheidung:** Multi-Provider-Architektur beibehalten (Mistral primär).
- **Begründung:** Flexibilität, Redundanz, Austauschbarkeit. Provider-Schnittstelle (`LLMProvider`) existiert bereits.

## R-07: Memory

- **Optionen:** Nur ConversationManager, SQLite, Vector DB, Kombination
- **Entscheidung:** Kombination aus SQLite (strukturierte Daten) + ChromaDB/FAISS (Vector DB) + Sentence Transformers (Embeddings).
- **Begründung:** Langfristiges Gedächtnis erfordert semantische Suche + strukturierte Fakten.

## R-08: Plugin-Architektur

- **Optionen:** Eigener Plugin-Loader, ovos-plugin-manager
- **Entscheidung:** `ovos-plugin-manager` als Abstraktion für Voice-Komponenten; eigener Plugin-Loader für TARNO-spezifische Tools.
- **Begründung:** OPM standardisiert STT/TTS/Wake-Word/Microphone; TARNO-Tools sind spezifisch und benötigen eigene Interface-Definition.

---

# 12. End Vision

TARNO wird eine modulare KI-Agent-Plattform, die so nah wie technisch möglich an Tony Starks J.A.R.V.I.S. herankommt:

**OpenVoiceOS Core + ovos-bus** + **TARNO-Persona/Solver** + **openWakeWord** + **faster-whisper** + **Piper TTS** + **Multi-Provider LLM** + **Memory** + **Vision** + **Tool Ecosystem**

Ziel: Ein professioneller, persönlicher KI-Sprachassistent mit TARNO-Persönlichkeit, der Sprache, Bildschirm, Kamera und Systemaktionen versteht und ausführt.
