"""Routine runner for recurring multi-step user workflows."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)


@dataclass
class RoutineStep:
    tool: str
    params: dict[str, Any]


@dataclass
class Routine:
    id: str
    name: str
    trigger_phrase: str
    steps: list[RoutineStep]
    enabled: bool = True


class RoutineRunner:
    """Discovers, stores and executes voice-triggered routines."""

    def __init__(
        self,
        tool_executor: Callable[[str, dict[str, Any]], Any],
        storage_path: Path | str = "~/.tarno/routines.json",
    ) -> None:
        self._tool_executor = tool_executor
        self._path = Path(storage_path).expanduser()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._routines: dict[str, Routine] = {}
        self._load()

    def register(self, routine: Routine) -> None:
        self._routines[routine.id] = routine
        self._save()

    def match(self, user_text: str) -> Routine | None:
        lower = user_text.lower()
        for routine in self._routines.values():
            if routine.enabled and routine.trigger_phrase.lower() in lower:
                return routine
        return None

    def run(self, routine: Routine) -> list[Any]:
        log.info("Routine ausführen: %s (%d Schritte)", routine.name, len(routine.steps))
        results: list[Any] = []
        for step in routine.steps:
            try:
                result = self._tool_executor(step.tool, step.params)
                results.append(result)
            except Exception as exc:
                log.exception("Routine-Schritt fehlgeschlagen: %s", step.tool)
                results.append(f"Fehler: {exc}")
        return results

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            for item in raw:
                steps = [RoutineStep(**s) for s in item.pop("steps", [])]
                routine = Routine(steps=steps, **item)
                self._routines[routine.id] = routine
        except Exception:
            log.exception("Routinen konnten nicht geladen werden")

    def _save(self) -> None:
        data = []
        for r in self._routines.values():
            entry = {
                "id": r.id,
                "name": r.name,
                "trigger_phrase": r.trigger_phrase,
                "enabled": r.enabled,
                "steps": [{"tool": s.tool, "params": s.params} for s in r.steps],
            }
            data.append(entry)
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
