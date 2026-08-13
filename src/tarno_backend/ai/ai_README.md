# `tarno_backend/ai/` — LLM providers, tools, and conversation handling

Everything related to talking to a language model: which provider is used,
how tool-calling works, how conversations are kept within context limits,
and the guardrails around persona and response quality.

## Layout

- **Providers** (`provider.py` = abstract interface; `claude_client.py`,
  `mistral_client.py`, `gemini_client.py`, `groq_client.py`,
  `huggingface_client.py`, `ollama_client.py`, `openai_compatible.py` =
  concrete implementations): each wraps one LLM API behind the same
  interface. `openai_compatible.py` is the generic fallback for any
  OpenAI-compatible endpoint (covers most of the free-tier providers).
- **`factory.py`**: central place that builds a provider (or a fallback
  chain of providers) from config + `SecretsVault` — this is where API
  keys actually get resolved, not in the individual clients.
- **`fallback_provider.py`**: chains multiple providers so a failure on one
  falls through to the next.
- **`conversation.py`**: conversation/history state.
- **`summarizer.py`**: compresses long conversation history to stay inside
  the context window (see also `context/` for token-usage tracking).
- **`streaming.py`**: helpers for consuming/accumulating streamed responses.
- **`persona_guard.py`** / **`response_guard.py`**: keep TARNO's persona
  from drifting and strip unwanted patterns (e.g. premature farewells)
  from responses.
- **`tool_registry.py`**: registers the tools an LLM can invoke via native
  tool-use.
- **`model_catalog.py`**: curated per-provider model list surfaced in the
  WinUI model picker.

## Subpackages

- **`coding/`**: the coding-agent backend (native tool-calling loop +
  optional `aider` adapter) used by the WinUI coding panel — see
  `dispatcher.py` for how a backend is chosen and `native_agent.py` for the
  default implementation.
- **`context/`**: output compression and token-usage tracking to keep
  requests within a provider's context window.
- **`pool/`**: multi-agent "pool" orchestration (parallel worker agents),
  see `orchestrator.py` / `worker.py`.
- **`prompts/`**: system prompt builders, one per surface (chat, coding,
  proactive, TTS voice, pool).

## Cross-references

- Provider/config decisions: [`workspace/debug/docs/adr/ADR-002-OVOS-Dependency.md`](../../../workspace/debug/docs/adr/ADR-002-OVOS-Dependency.md)
- Known issues/history: [`workspace/debug/docs/technical-debt-catalog.md`](../../../workspace/debug/docs/technical-debt-catalog.md) (TD-004: API-key handling, TD-014: no token counting)
- API keys are resolved via `tarno_backend/security/secrets.py` (`SecretsVault`), never read directly from `os.environ` in the clients themselves (TD-004).
- Tools registered into `tool_registry.py` by other subsystems: `tarno_backend/browser/` (see `browser_README.md`), `tarno_backend/desktop/` (see `desktop_README.md`), `tarno_backend/plugins/` (see `plugins_README.md`) and the concrete integrations under `tarno_backend/integrations/` (see `integrations_README.md`).
- Background thread that actually calls providers from the voice loop: `tarno_backend/workers/llm_worker.py` (see `workers_README.md`)
