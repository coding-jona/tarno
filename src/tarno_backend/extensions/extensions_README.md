# `tarno_backend/extensions/` — autonomous background features

Cognitive/autonomous layer built on top of `TarnoEngine`: things TARNO does on
its own initiative (reminders, routines, multi-step task plans) rather than
in direct response to a user utterance. Per `CLAUDE.md`'s architecture rule,
these are kept as separate layers on top of the execution engine, not folded
into it.

## Files

- **`coordinator.py`**: bundles all autonomous TARNO extensions into one
  entry point — starts/stops the scheduler, reminder engine, routines and
  task planner together.
- **`scheduler.py`**: generic background scheduler underlying briefings,
  reminders and routines.
- **`reminder.py`**: time- and condition-based user reminders.
- **`routines.py`**: runner for recurring multi-step user workflows (e.g. a
  morning briefing routine).
- **`task_planner.py`**: multi-step autonomous action planning with a
  human-in-the-loop confirmation step before anything destructive runs.
- **`rollback.py`**: file-operation rollback for multi-step autonomous tasks,
  so a task planner run that fails partway through can be undone.

## Cross-references

- Execution layer these extensions sit on top of: `tarno_backend/core/engine.py`
  (see `core_README.md`) — do not replace `TarnoEngine` itself here.
- Permission confirmation for task-planner actions: `tarno_backend/grpc/server.py`
  (see `grpc_README.md`)
