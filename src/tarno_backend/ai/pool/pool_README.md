# `tarno_backend/ai/pool/` — Agent-Pool (multi-agent collaboration)

Lets multiple LLM providers collaborate on one coding task in parallel: a
lead agent decomposes the task, worker agents (each backed by a different
provider) work their assigned piece, and the lead merges the results. Not
the same as `tarno_backend/ai/coding/`, which this builds on top of for the
actual single-agent code editing.

## Files

- **`models.py`**: data model for the Agent-Pool feature.
- **`orchestrator.py`**: `PoolOrchestrator` — runs the
  Decompose → Assign → Collect → Merge loop across the lead and workers.
- **`worker.py`**: `PoolWorker` — wraps one `LLMProvider` for one pool slot.
- **`edit_apply.py`**: applies the lead's final, merged instruction over the
  workspace via the coding tools.
- **`exceptions.py`**: exceptions raised by this subsystem.

## Cross-references

- Single-agent backend this builds on: [`ai/coding/`](../coding/coding_README.md)
- System prompts for lead/worker roles: `tarno_backend/ai/prompts/pool_system.py`
  (see [`prompts_README.md`](../prompts/prompts_README.md))
- gRPC surface (`test_pool_grpc.py` in the test suite): `tarno_backend/grpc/server.py`
  (see `grpc_README.md`)
