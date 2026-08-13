# TARNO Zeitaufwandschätzung (P0–P2)

**Endziel:** Funktionierender TARNO-Agent mit `ovos-core` als Brain, Wake-Word, lokaler Voice-Pipeline, Memory, Tools, Browser-Automation, Vision und Multi-Step-Agent.

**Annahmen:**
- Konzentrierte Vollzeit-Arbeit (40h/Woche)
- Ein erfahrener Python-Entwickler mit Erfahrung in Voice/AI
- ovos-core läuft auf Windows mit vertretbarem Aufwand
- Keine Hardware-Beschaffung oder Modell-Training als große Blocker

## Phasenschätzung

| Phase | Inhalt | Aufwand | Risiken |
|-------|--------|---------|---------|
| Phase 1 | Foundation: ovos-core, ovos-bus, ovos-listener, Plugin-Manager, Config, Logging | 1–2 Wochen | Windows-Kompatibilität von ovos-core kann +1–2 Wochen kosten |
| Phase 2 | Voice Pipeline: openWakeWord, Microphone, faster-whisper, Piper TTS | 2–3 Wochen | Audio-Latenz, Windows-Mikrofon-Probleme, Modell-Größe |
| Phase 3 | Persona / LLM: TARNO-Persona, Mistral-Integration, Multi-Provider, Prompts | 2–3 Wochen | Tool-Call-Format, Kontextmanagement, API-Kosten |
| Phase 4 | Agent Framework: Memory (SQLite + Vector DB), Tool-Registry, Permissions | 3–4 Wochen | Embedding-Qualität, Tool-Sandbox, Security |
| Phase 5 | Advanced: Browser-Automation, Screenshot, Webcam, Multi-Step-Agent | 4–6 Wochen | Playwright-Windows, Vision-Modell-Kosten, Zuverlässigkeit |

## Gesamtschätzung

**P0–P2 Endziel: 12–18 Wochen Vollzeit** (ca. 3–4,5 Monate)

**Pufferfaktoren, die es verlängern können:**
- Windows-spezifische Probleme mit ovos-core: +2–4 Wochen
- Eigenes Wake-Word-Training: +1–2 Wochen
- Lokale TTS-Optimierung (Piper): +1 Woche
- Langzeit-Memory + Embeddings: +1–2 Wochen
- Multi-Step-Agent Zuverlässigkeit: +2–3 Wochen

## Wichtiger Hinweis

Ein **1:1-Iron-Man-TARNO** ist mit heutiger Technologie nicht realisierbar (echte AGI, holografische Projektion, vollständige Autonomie). Die obige Schätzung bezieht sich auf die **realistische P0–P2-Roadmap**, die einen beeindruckenden, nützlichen persönlichen KI-Agenten liefert.

## Minimaler erster Meilenstein

Bereits nach **2–4 Wochen** sollte eine erste funktionierende Kette stehen:

`Hey TARNO` → Wake-Word → STT → LLM → TTS

Dies ist der schnellste Erfolg, um das Projekt voranzutreiben und Feedback zu sammeln.
