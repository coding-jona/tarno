# `tarno_backend/core/` — engine, config, and command execution

The backbone of the backend: the main orchestrator, the config system, and
the command-execution/permission machinery that everything else plugs into.

## Key files

- **`engine.py`**: the main orchestrator — wires voice, AI, memory,
  integrations etc. together and runs the voice loop. This is the entry
  point most other subsystems get constructed by/registered into.
- **`ovos_engine.py`**: OpenVoiceOS-bus variant of the engine (used in
  `--no-gui` mode, see `requirements-ovos.txt` / ADR-002).
- **`config.py`**: centralized `TarnoConfig` dataclass hierarchy, loaded
  from `config/default.yaml` + a user override file, YAML in/out. Writes
  are atomic (temp file + `os.replace`, `.bak` fallback on load — see
  TD-001) since a crash mid-write used to corrupt the config.
- **`voice_controller.py`**: framework-agnostic voice pipeline with a
  formal state machine and a watchdog thread that force-restarts the
  voice loop if it hangs (not just crashes) — see TD-002.
- **`command_engine.py`** + **`command_tool.py`** + **`executor.py`**:
  the command-execution pipeline — `command_tool.py` exposes it to the
  LLM as a callable tool, `command_engine.py` is the actual risk-tiered
  execution logic, `executor.py` is the shell backend.
- **`permission_service.py`**: gates risky command/voice actions behind
  user confirmation. In the gRPC/WinUI launch mode this round-trips
  through `PermissionDialog` in the frontend instead of blocking on
  `input()` (see TD-025 — this used to hang forever in headless mode).
- **`service_mediator.py`**: bridges the (deprecated) PySide6 GUI to the
  backend workers. **Imports `PySide6` unconditionally** — only relevant
  if the legacy `--legacy-ui` fallback path is exercised (see
  `tarno_backend/gui/gui_README.md`, `tarno_backend/ui/ui_README.md`).
- **`agent_service.py`**: runs the TARNO agent on the OVOS bus.
- **`proactive_engine.py`** + **`proactive_briefing.py`**: autonomous
  triggers and scheduled spoken briefings (calendar-aware via
  `calendar_service.py`).
- **`process_sandbox.py`**: Win32 Job Object sandboxing for subprocesses
  spawned by the command engine.
- **`events.py`**: a small synchronous event bus used for loose coupling
  between subsystems (avoids direct imports across packages).
- **`session.py`** / **`workspace.py`**: conversation-turn/session
  context and multi-root workspace path resolution + sandbox checks.
- **`retry.py`** / **`action_logger.py`** / **`action_result.py`** /
  **`exceptions.py`**: small shared utilities (backoff retry, audit
  logging, a common result contract, domain exceptions).

## Cross-references

- Architecture decisions: [`workspace/debug/docs/adr/`](../../../workspace/debug/docs/adr/)
- Known issues/history: [`workspace/debug/docs/technical-debt-catalog.md`](../../../workspace/debug/docs/technical-debt-catalog.md) (most TD-00x entries touch this folder)
- gRPC bridge that exposes this engine to the WinUI frontend: `tarno_backend/grpc/` (see `grpc_README.md`)
- Background threads `engine.py` coordinates: `tarno_backend/workers/` (see `workers_README.md`)
- Autonomous layer built on top of the engine (do not fold into `engine.py` itself): `tarno_backend/extensions/` (see `extensions_README.md`)
- Path resolution used by `config.py`: `tarno_backend/utils/paths.py` (see `utils_README.md`) — note `ovos_engine.py`'s `_BUNDLE_ROOT` deliberately does *not* use it (PyInstaller-bundle compatibility)
