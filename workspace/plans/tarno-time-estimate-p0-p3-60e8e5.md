# TARNO Zeitaufwandschätzung (P0–P3)

**Endziel:** TARNO-Agent mit allen priorisierten Features aus der Iron-Man-Roadmap, inklusive P3: proaktiven Briefings und holografischem UI-Overlay.

**Annahmen:**
- Konzentrierte Vollzeit-Arbeit (40h/Woche)
- Erfahrener Python-Entwickler mit Voice/AI/Frontend-Erfahrung
- ovos-core läuft auf Windows mit vertretbarem Aufwand
- Holografisches UI bedeutet: moderates Overlay (Electron, Three.js/WebGL, Audio-Visualisierungen, HUD-Widgets)

## Phasenschätzung (P0–P3)

| Phase | Inhalt | Aufwand | Risiken |
|-------|--------|---------|---------|
| Phase 1 | Foundation: ovos-core, ovos-bus, ovos-listener, Plugin-Manager, Config, Logging | 1–2 Wochen | Windows-Kompatibilität von ovos-core kann +1–2 Wochen kosten |
| Phase 2 | Voice Pipeline: openWakeWord, Microphone, faster-whisper, Piper TTS | 2–3 Wochen | Audio-Latenz, Windows-Mikrofon-Probleme, Modell-Größe |
| Phase 3 | Persona / LLM: TARNO-Persona, Mistral-Integration, Multi-Provider, Prompts | 2–3 Wochen | Tool-Call-Format, Kontextmanagement, API-Kosten |
| Phase 4 | Agent Framework: Memory (SQLite + Vector DB), Tool-Registry, Permissions | 3–4 Wochen | Embedding-Qualität, Tool-Sandbox, Security |
| Phase 5 | Advanced: Browser-Automation, Screenshot, Webcam, Multi-Step-Agent | 4–6 Wochen | Playwright-Windows, Vision-Modell-Kosten, Zuverlässigkeit |
| Phase 6 | Proaktive Briefings: Zeitgesteuerte Zusammenfassungen, Kalender-Integration, Morning Digest | 2–3 Wochen | Scheduling-Zuverlässigkeit, API-Zugriff (Kalender, E-Mail) |
| Phase 7 | Holografisches UI: Electron-Overlay, Three.js/WebGL-HUD, Audio-Visualisierungen, Always-on-Top | 6–10 Wochen | Frontend-Komplexität, Performance, Windows-Overlay-Verhalten, Design |

## Gesamtschätzung

**P0–P3 Endziel: 20–31 Wochen Vollzeit** (ca. 5–8 Monate)

**Mit Puffer für Windows-Probleme, UI-Iterationen und Tests:**
- **Realistisch:** 24–36 Wochen (6–9 Monate)

## Vergleich P0–P2 vs. P0–P3

| Scope | Aufwand | Zeit | End-Ergebnis |
|-------|---------|------|--------------|
| P0–P2 | 12–18 Wochen | 3–4,5 Monate | Funktioneller Agent, aber ohne aktives UI und proaktive Briefings |
| P0–P3 | 20–31 Wochen | 5–8 Monate | Vollständiger TARNO-Erlebnis mit visuellem Overlay und autonomen Briefings |

## Wichtiger Hinweis

Auch P0–P3 ist **kein 1:1-Iron-Man-TARNO**. Einige filmische Fähigkeiten (echte künstliche Allgemeinintelligenz, frei schwebende Hologramme, vollständig autonome Roboter-Steuerung) sind mit heutiger Technik nicht realisierbar. Die Schätzung deckt das **bestmögliche real-world TARNO-Erlebnis** ab.

## Empfehlung

1. **Zuerst P0–P2 umsetzen** (erste 3–4,5 Monate)
2. **Dann P3 evaluieren** — vor allem, ob das holografische UI den Mehraufwand rechtfertigt
3. **Falls P3 gestartet wird:** UI-Design zuerst als Prototyp, bevor große Teile implementiert werden
