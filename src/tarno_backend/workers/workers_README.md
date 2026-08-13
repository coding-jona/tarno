# `tarno_backend/workers/` — background threads for the voice pipeline

Thread wrappers that keep long-running, blocking work (LLM calls, TTS
synthesis, wake-word/ASR) off the main engine loop. Each worker owns one
concern; `tarno_backend/core/engine.py` coordinates them.

## Files

- **`voice_worker.py`**: background thread for wake-word detection and
  speech recognition (the input side of the voice pipeline).
- **`llm_worker.py`**: background thread for LLM provider calls.
- **`tts_worker.py`**: background thread for text-to-speech synthesis (the
  output side of the voice pipeline).

## Cross-references

- Coordinating engine: `tarno_backend/core/engine.py` (see `core_README.md`)
- Full audio pipeline context: `tarno_backend/voice/` (see `voice_README.md`)
- LLM providers called from `llm_worker.py`: `tarno_backend/ai/` (see `ai_README.md`)
