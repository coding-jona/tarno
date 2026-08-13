"""File-operation rollback for multi-step autonomous tasks (Block 5, Phase 45).

If a later step in a TaskPlanner-executed multi-step task fails, the already-
completed file-mutating steps in that same task run are undone in reverse
order, so a partially-failed autonomous plan doesn't leave the filesystem in
an inconsistent half-applied state.

Deliberately scoped to the file tools this project actually registers
(write_file, delete_file, copy_file, move_file, create_directory) - not
arbitrary shell commands (execute_command), whose side effects are open-ended
and not mechanically reversible in general. Each snapshotter runs BEFORE its
step executes, capturing enough pre-state to undo it; every undo callable is
defensively idempotent (checks current filesystem state before acting), so
recording a snapshot for a step that then itself fails is harmless.
"""

from __future__ import annotations

import logging
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)

_SNAPSHOT_ROOT = Path("~/.tarno/rollback_snapshots").expanduser()

Snapshotter = Callable[[dict[str, Any]], "Callable[[], None] | None"]


def _snapshot_write_file(params: dict[str, Any]) -> Callable[[], None] | None:
    path = Path(params.get("filepath", "")).expanduser()
    if not path.exists():
        def undo() -> None:
            if path.exists():
                path.unlink()
        return undo

    backup = _SNAPSHOT_ROOT / f"{uuid.uuid4().hex}_{path.name}"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup)

    def undo() -> None:
        shutil.copy2(backup, path)
        backup.unlink(missing_ok=True)
    return undo


def _snapshot_delete_file(params: dict[str, Any]) -> Callable[[], None] | None:
    path = Path(params.get("filepath", "")).expanduser()
    if not path.exists():
        return None  # nothing to delete, nothing to undo

    backup = _SNAPSHOT_ROOT / f"{uuid.uuid4().hex}_{path.name}"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup)

    def undo() -> None:
        if not path.exists():
            shutil.copy2(backup, path)
        backup.unlink(missing_ok=True)
    return undo


def _snapshot_create_directory(params: dict[str, Any]) -> Callable[[], None] | None:
    path = Path(params.get("path", "")).expanduser()
    if path.exists():
        return None  # already existed - not this step's to remove

    def undo() -> None:
        if path.exists() and not any(path.iterdir()):
            path.rmdir()
    return undo


def _snapshot_copy_file(params: dict[str, Any]) -> Callable[[], None] | None:
    dst = Path(params.get("destination", "")).expanduser()
    if dst.exists():
        return None  # would overwrite an existing file - out of scope, don't touch

    def undo() -> None:
        if dst.exists():
            dst.unlink()
    return undo


def _snapshot_move_file(params: dict[str, Any]) -> Callable[[], None] | None:
    src = Path(params.get("source", "")).expanduser()
    dst = Path(params.get("destination", "")).expanduser()

    def undo() -> None:
        if dst.exists() and not src.exists():
            shutil.move(str(dst), str(src))
    return undo


_SNAPSHOTTERS: dict[str, Snapshotter] = {
    "write_file": _snapshot_write_file,
    "delete_file": _snapshot_delete_file,
    "create_directory": _snapshot_create_directory,
    "copy_file": _snapshot_copy_file,
    "move_file": _snapshot_move_file,
}


@dataclass
class RollbackJournal:
    """Tracks undo callables for a single task run, in execution order."""

    _undo_stack: list[tuple[str, Callable[[], None]]] = field(default_factory=list)

    def record(self, tool_name: str, params: dict[str, Any]) -> None:
        """Snapshot pre-step state for *tool_name*, if it's a known-reversible
        tool. Call this BEFORE the step actually executes."""
        snapshotter = _SNAPSHOTTERS.get(tool_name)
        if snapshotter is None:
            return
        try:
            undo = snapshotter(params)
        except Exception:
            log.exception("Rollback-Snapshot für %s fehlgeschlagen", tool_name)
            return
        if undo is not None:
            self._undo_stack.append((tool_name, undo))

    def rollback(self) -> int:
        """Undo all recorded steps in reverse order. Returns count undone."""
        undone = 0
        for tool_name, undo in reversed(self._undo_stack):
            try:
                undo()
                undone += 1
                log.info("Rollback: '%s' rückgängig gemacht", tool_name)
            except Exception:
                log.exception("Rollback für '%s' fehlgeschlagen", tool_name)
        self._undo_stack.clear()
        return undone
