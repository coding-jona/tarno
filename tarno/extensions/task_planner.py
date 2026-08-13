"""Task planner for multi-step autonomous actions with human-in-the-loop."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from tarno.core.action_result import ActionResult
from tarno.extensions.rollback import RollbackJournal

log = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PlannedTask:
    id: str
    description: str
    status: TaskStatus
    created_at: datetime
    steps: list[dict[str, Any]] = field(default_factory=list)
    approved_at: datetime | None = None
    result: ActionResult | None = None


class TaskPlanner:
    """Plans, persists and executes multi-step tasks requiring approval."""

    def __init__(
        self,
        approval_callback: Callable[[PlannedTask], bool],
        executor: Callable[[str, dict[str, Any]], Any],
        storage_path: Path | str = "~/.tarno/tasks.json",
    ) -> None:
        self._approval = approval_callback
        self._executor = executor
        self._path = Path(storage_path).expanduser()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._tasks: dict[str, PlannedTask] = {}
        self._load()

    def create(self, description: str, steps: list[dict[str, Any]]) -> PlannedTask:
        task = PlannedTask(
            id=str(uuid.uuid4()),
            description=description,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            steps=steps,
        )
        self._tasks[task.id] = task
        self._save()
        log.info("Aufgabe geplant: %s", task.id)
        return task

    def run(self, task_id: str) -> PlannedTask:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Aufgabe {task_id} nicht gefunden")

        if task.status != TaskStatus.PENDING and task.status != TaskStatus.APPROVED:
            return task

        if task.status == TaskStatus.PENDING:
            approved = self._approval(task)
            if approved is None:
                log.info("Aufgabe %s wartet auf Genehmigung", task_id)
                return task
            if not approved:
                task.status = TaskStatus.CANCELLED
                self._save()
                return task
            task.status = TaskStatus.APPROVED
            task.approved_at = datetime.now()

        return self._execute(task)

    def approve(self, task_id: str) -> PlannedTask:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Aufgabe {task_id} nicht gefunden")
        if task.status != TaskStatus.PENDING:
            return task
        task.status = TaskStatus.APPROVED
        task.approved_at = datetime.now()
        self._save()
        return self._execute(task)

    def reject(self, task_id: str) -> PlannedTask:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Aufgabe {task_id} nicht gefunden")
        task.status = TaskStatus.CANCELLED
        self._save()
        return task

    def list_pending(self) -> list[PlannedTask]:
        return [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]

    def _execute(self, task: PlannedTask) -> PlannedTask:
        task.status = TaskStatus.RUNNING
        self._save()

        # Block 5, Phase 45: if a later step fails, already-completed
        # file-mutating steps in THIS task run are rolled back so a
        # partially-failed multi-step plan doesn't leave the filesystem in an
        # inconsistent half-applied state. Scoped to file tools only (see
        # tarno/extensions/rollback.py) - shell commands aren't mechanically
        # reversible in general.
        journal = RollbackJournal()

        for step in task.steps:
            tool_name = step["tool"]
            params = step.get("params", {})
            journal.record(tool_name, params)  # snapshot pre-state before running
            try:
                result = self._executor(tool_name, params)
                if isinstance(result, ActionResult) and not result.success:
                    task.status = TaskStatus.FAILED
                    task.result = result
                    self._rollback_and_log(journal)
                    self._save()
                    return task
            except Exception as exc:
                log.exception("Aufgaben-Schritt fehlgeschlagen")
                task.status = TaskStatus.FAILED
                task.result = ActionResult(success=False, message=str(exc), error_code="ExecutionError")
                self._rollback_and_log(journal)
                self._save()
                return task

        task.status = TaskStatus.COMPLETED
        task.result = ActionResult(success=True, message="Aufgabe abgeschlossen")
        self._save()
        return task

    @staticmethod
    def _rollback_and_log(journal: RollbackJournal) -> None:
        undone = journal.rollback()
        if undone:
            log.info(
                "Rollback nach fehlgeschlagenem Schritt: %d Aktion(en) rückgängig gemacht",
                undone,
            )

    def list_tasks(self) -> list[PlannedTask]:
        return sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            for item in raw:
                item["created_at"] = datetime.fromisoformat(item["created_at"])
                item["approved_at"] = (
                    datetime.fromisoformat(item["approved_at"])
                    if item.get("approved_at")
                    else None
                )
                item["status"] = TaskStatus(item["status"])
                task = PlannedTask(**item)
                self._tasks[task.id] = task
        except Exception:
            log.exception("Aufgaben konnten nicht geladen werden")

    def _save(self) -> None:
        data = []
        for t in self._tasks.values():
            result: dict[str, Any] | None = None
            if t.result is not None:
                result = {
                    "success": t.result.success,
                    "message": t.result.message,
                    "error_code": t.result.error_code,
                    "details": t.result.details,
                }
            entry = {
                "id": t.id,
                "description": t.description,
                "status": t.status.value,
                "created_at": t.created_at.isoformat(),
                "approved_at": t.approved_at.isoformat() if t.approved_at else None,
                "steps": t.steps,
                "result": result,
            }
            data.append(entry)
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
