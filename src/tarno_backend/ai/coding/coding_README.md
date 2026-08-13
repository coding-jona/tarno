# `tarno_backend/ai/coding/` — coding-agent backend

Powers the WinUI coding panel: lets TARNO read/edit/run code in a workspace
on the user's behalf, as a native tool-calling loop with an optional `aider`
adapter. Not related to `tarno_backend/ai/pool/` (multi-agent collaboration)
— this is the single-agent coding backend `pool/` builds on top of.

## Files

- **`protocol.py`**: shared protocol/interface every coding backend adapter
  implements (native and `aider`).
- **`dispatcher.py`**: picks the concrete backend for the configured
  provider/backend setting — the entry point that decides "native or aider".
- **`agent.py`**: `native_agent.py`'s counterpart referenced from
  `ai_README.md` — the high-level coding agent used by the engine and gRPC
  bridge, wired through `dispatcher.py`.
- **`native_tools.py`**: the tool set (read/write/list/run) exposed to the
  native agentic backend.
- **`tool.py`**: registers the `coding_task` tool with `tool_registry.py` so
  the LLM can invoke a coding run as a normal tool call.
- **`io_capture.py`**: captures `aider`'s progress output and forwards it as
  TARNO events (so the WinUI panel can stream progress live).
- **`exceptions.py`**: exceptions raised by this subsystem.

## Cross-references

- Parent package overview: [`ai_README.md`](../ai_README.md)
- gRPC surface: `tarno_backend/grpc/server.py` (see `grpc_README.md`)
- Related multi-agent orchestration: [`ai/pool/`](../pool/pool_README.md)
