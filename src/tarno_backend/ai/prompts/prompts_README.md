# `tarno_backend/ai/prompts/` — layered system-prompt builders

One system prompt per surface, assembled by a shared layered builder rather
than duplicated ad hoc strings scattered through the codebase.

## Files

- **`builder.py`**: the layered system-prompt builder every prompt module
  below is composed through.
- **`chat_system.py`**: system prompt for normal chat mode.
- **`code_system.py`**: system prompt for code mode (used by
  `tarno_backend/ai/coding/`).
- **`pool_system.py`**: system prompts for the Agent-Pool's lead/worker
  roles (used by `tarno_backend/ai/pool/`).
- **`proactive_system.py`**: rephrases/embellishes autonomous
  `ProactiveEngine` drafts before they're spoken — keeps unsolicited TARNO
  output in-persona.
- **`tts_voice_prompt.py`**: TTS-specific prompt generation for the
  Thorsten/Piper voice.

## Cross-references

- Parent package overview: [`ai_README.md`](../ai_README.md)
- Persona-drift guardrails applied on top of these prompts: `persona_guard.py`
  / `response_guard.py` (see `ai_README.md`)
- Proactive triggers that use `proactive_system.py`: `tarno_backend/core/proactive_engine.py`
  (see `core_README.md`)
