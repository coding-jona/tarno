# `tarno_backend/memory/` — long-term memory, retrieval, preferences

TARNO's knowledge base: facts extracted from conversation, learned user
preferences, and semantic search over ingested content — all CPU-only,
local, no external services.

## Files

- **`store.py`**: SQLite-backed storage for facts, episodes and preferences
  — the actual persistence layer everything else here reads/writes through.
- **`embeddings.py`**: local ONNX text embeddings for semantic search (no
  API calls, runs on CPU).
- **`chunking.py`**: splits text into chunks for the knowledge base.
- **`ingest.py`**: ingests a directory/workspace into the knowledge base.
- **`fact_extractor.py`**: automatically pulls facts out of user messages
  during normal conversation.
- **`preferences.py`**: learns user preferences from explicit statements
  and repeated patterns (distinct from `fact_extractor.py` — preferences
  vs. facts).
- **`retrieval.py`**: combines keyword search + semantic similarity +
  recency to answer "what do we know about X".
- **`privacy.py`**: privacy controls over what gets stored/retrieved.
- **`knowledge_base.py`**: CPU-only knowledge base specifically for the
  coding assistant (`tarno_backend/ai/coding/`), separate from the general
  conversational memory above.
- **`inspector.py`**: CLI tool to inspect and manually correct what
  TARNO has stored in long-term memory.

## Cross-references

- Feeds into: `tarno_backend/ai/conversation.py` and `tarno_backend/ai/coding/` (via `knowledge_base.py`)
- Test coverage: [`workspace/debug/docs/test-coverage-report.md`](../../../workspace/debug/docs/test-coverage-report.md) rates this "Basis" (11 tests) — check before large refactors.
