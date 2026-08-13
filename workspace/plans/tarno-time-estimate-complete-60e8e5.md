# TARNO Realistische Zeitaufwandschätzung (P0–P3 + Prioritäten + Fein-Tuning)

**Endziel:** Vollständiger P0–P3 TARNO-Agent mit viel Zeit für Priorisierung, Iteration, Fein-Tuning, Tests und Polishing.

**Annahmen:**
- Konzentrierte Vollzeit-Arbeit (40h/Woche)
- Erfahrener Python-Entwickler mit Voice/AI/Frontend-Erfahrung
- ovos-core läuft auf Windows mit vertretbarem Aufwand
- Regelmäßige Planungs- / Priorisierungsrunden (kein stures Abarbeiten)

## Basis-Implementierung (P0–P3)

| Phase | Inhalt | Aufwand |
|-------|--------|---------|
| Phase 1 | Foundation: ovos-core, ovos-bus, ovos-listener, Plugin-Manager, Config, Logging | 1–2 Wochen |
| Phase 2 | Voice Pipeline: openWakeWord, Microphone, faster-whisper, Piper TTS | 2–3 Wochen |
| Phase 3 | Persona / LLM: TARNO-Persona, Mistral-Integration, Multi-Provider, Prompts | 2–3 Wochen |
| Phase 4 | Agent Framework: Memory, Tool-Registry, Permissions | 3–4 Wochen |
| Phase 5 | Advanced: Browser, Screenshot, Webcam, Multi-Step-Agent | 4–6 Wochen |
| Phase 6 | Proaktive Briefings: Zeitgesteuerte Zusammenfassungen, Kalender-Integration | 2–3 Wochen |
| Phase 7 | Holografisches UI: Electron-Overlay, Three.js/WebGL-HUD, Audio-Visualisierungen | 6–10 Wochen |
| **Subtotal Basis** | | **20–31 Wochen** |

## Zusätzliche realistische Kosten

**A. Fein-Tuning & Optimierung (20–35%)**
- Wake-Word-Threshold- und Modell-Tuning
- **Wake-Word-UX:** "Tarno" + sofortiges Weitersprechen ohne Wartezeit, mit Toleranz für natürliche Denkpausen (kein harter VAD-Cutoff)
- STT-Qualitäts-Optimierung (Sprache, Modell, VAD)
- TTS-Stimme, Geschwindigkeit, Natürlichkeit
- LLM-Prompt-Engineering und Tool-Call-Zuverlässigkeit
- Performance-Optimierung (CPU-Last, RAM, Latenz)

**B. Tests, Bugs & Edge Cases (15–25%)**
- Windows-spezifische Fehler
- Audio-Hardware-Kompatibilität
- LLM-Fehlverhalten und Recovery
- Tool-Timeouts und Sandbox-Probleme
- Real-World-Szenarien (Hintergrundgeräusche, schlechtes Mikrofon)

**C. Iteration & Feedback (10–20%)**
- Anpassungen nach Tests
- Neue Prioritäten während der Entwicklung
- Umplanungen, wenn Technologien nicht wie erwartet funktionieren

**D. Dokumentation, Packaging & Deployment (5–10%)**
- Installer, PyInstaller, Konfiguration
- Dokumentation für Nutzer
- Logging und Monitoring

## Gesamtschätzung

| Ansatz | Aufwand | Zeit | Geeignet für |
|--------|---------|------|--------------|
| P0–P2 | 12–18 Wochen | 3–4,5 Monate | Minimaler funktioneller Agent |
| P0–P3 | 20–31 Wochen | 5–8 Monate | Vollständiges Erlebnis mit UI |
| P0–P3 + Prioritäten + Fein-Tuning | **29–50 Wochen** | **7–12 Monate** | Professionelles, poliertes Produkt |

## Realistische Empfehlung

- **7–9 Monate** für ein stabiles, gut nutzbares P0–P3-Produkt
- **10–12 Monate** für ein hochpoliertes, täglich nutzbares TARNO-Erlebnis mit minimalem Fehlverhalten

## Wichtig

Auch diese Schätzung ist **kein 1:1-Iron-Man-TARNO**. Einige filmische Fähigkeiten (echte AGI, echte Hologramme) sind heute nicht realisierbar. Die Schätzung deckt das **bestmögliche real-world TARNO-Erlebnis** ab.

## Roadmap / Versionen

**Version 0.1 – Foundation**
- Wake Word
- STT
- Mistral-Integration
- TTS
- Stabile Sprach-Konversation
- Grundlegende Tool-Ausführung
- Packaging & Installer
- Logging

**Version 0.2 – Productivity**
- Memory
- Kalender-Integration
- Proaktive Briefings
- Besseres Tool-Ökosystem
- Kontext-Verbesserungen
- Zuverlässigkeit

**Version 0.3 – Agent**
- Browser-Automation
- Vision / Screenshot-Analyse
- Multi-Step-Planning
- Besseres Reasoning
- Weitere Windows-Integrationen

**Version 1.0 – Production Ready**
- Performance-Optimierung
- Umfassende Tests
- Fehler-Recovery
- Konfigurations-Verbesserungen
- Dokumentation
- Security-Review
- Final Polishing

**Version 2.0 – Visual Experience (erst nach 1.0)**
- Holografisches UI
- Advanced Animations
- 3D-Visualisierungen
- Premium Visual Experience

## Vorschlag für den Start

1. **3–4 Monate** P0–P2 umsetzen
2. **2–3 Monate** Fein-Tuning und Stabilisierung
3. **Dann entscheiden**, ob P3 (UI + Briefings) den Aufwand rechtfertigt

## Notizen & Backlog

### Mistral-Modell-Strategie / Fallbacks
- **Aktueller Default:** `mistral-small-latest` bleibt die Standardeinstellung.
- **Mistral API Fehler 400:** War ein Bug in unserer Code-Seite (falsche Reihenfolge von Tool-Use- und Tool-Result-Nachrichten), kein Modell-Problem. Korrigiert.
- **Anfragen pro Sekunde:** Aktuell kein Engpass (Free Tier 1 req/s ist ausreichend für normale Sprachkonversation).
- **Optionale Fallbacks / Zukunftsideen (nur Notizen, keine Priorität):**
  - `mistral-small-2506` – naheliegender Update/Upgrade der aktuellen Small-Reihe.
  - `ministral-3b-2512` – sehr schnell, viele Anfragen (12.5 req/s), für einfache/kurze Anfragen oder Edge-Geräte geeignet.
  - `labs-leanstral-1-5-1` – experimentell, hohe Token-Rate, evtl. für längere Reasoning- oder Kontext-Anfragen.
  - `mistral-embed-2312` – **kein Chat-Modell**, nur für Embeddings. Nicht als Fallback für Konversationen geeignet.
- **Entscheidung:** Bei `mistral-small` bleiben. Für sehr lange/komplexe Anfragen können die oben genannten Modelle später evaluiert werden. Multi-Provider-Framework ist bereits vorhanden, daher einfach austauschbar.

### Webcam / Live-Sehen
- **Ziel:** TARNO soll die am PC angeschlossene Webcam nutzen können, um live zu "sehen" (z.B. Geste erkennen, Raum beschreiben, Objekt im Blickfeld finden).
- **Zuordnung:** Passend zu **Version 0.3 (Agent)** oder als erweitertes Vision-Feature.
- **Anforderung:** Muss mit einem 100% free Tier / kostenlosen Modell oder lokalen Lösung umgesetzt werden.
- **Mögliche Richtungen:**
  - Lokale multimodale Modelle (z.B. `LLaVA` via Ollama, `moondream`, `MiniCPM-V`).
  - Screenshot-ähnliche Frame-Extraktion aus dem Webcam-Stream.
  - OpenCV für Video-Capture + lokales VLM für Frame-Beschreibung.
- **Status:** Backlog / Zukunft. Erst nach stabiler Basis-LLM- und Vision-Infrastruktur (Screenshot) angehen.
