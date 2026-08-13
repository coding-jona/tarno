# `tarno_backend/voice/tts_engines/` — local TTS engine adapters

Pluggable text-to-speech backends behind one common interface
(`base.py`), selected/instantiated by `tarno_backend/voice/` based on config.

## Files

- **`base.py`**: abstract base class every engine below implements.
- **`piper.py`**: Piper TTS — fast local CPU synthesis with ONNX models.
  The default, CPU-first engine (see `CLAUDE.md`'s "CPU-first" constraint).
- **`neutts.py`**: NeuTTS Nano engine with local voice cloning.
- **`edge.py`**: network fallback using `edge-tts` and `gTTS` — used when no
  local engine is available or configured.

## Cross-references

- Parent package overview: [`voice_README.md`](../voice_README.md)
- Background thread that calls these: `tarno_backend/workers/tts_worker.py`
  (see `workers_README.md`)
- TTS-specific prompt generation: `tarno_backend/ai/prompts/tts_voice_prompt.py`
  (see `prompts_README.md`)
