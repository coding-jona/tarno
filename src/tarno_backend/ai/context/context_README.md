# `tarno_backend/ai/context/` — context-window efficiency

Keeps conversations and tool output within a provider's context window
without losing information the user actually cares about. Three
independent techniques, used together by `tarno_backend/ai/conversation.py`.

## Files

- **`output_compressor.py`**: RTK-inspired compression of large tool
  outputs before they re-enter the prompt (e.g. a huge file read or command
  output) — keeps the signal, drops the bulk.
- **`summarizer.py`**: recursive conversation-history summarizer using a
  dedicated small model, so summarization itself doesn't burn the main
  provider's context/cost budget. Same module referenced as
  `tarno_backend/ai/summarizer.py` in `ai_README.md` — that's the
  higher-level entry point, this is the recursive implementation detail.
- **`usage_tracker.py`**: tracks context-window usage so the rest of the
  system knows when it's approaching the limit and needs to compress or
  summarize.

## Cross-references

- Parent package overview: [`ai_README.md`](../ai_README.md)
- Known gap: TD-014 (no token counting) in
  [`workspace/debug/docs/technical-debt-catalog.md`](../../../../workspace/debug/docs/technical-debt-catalog.md)
