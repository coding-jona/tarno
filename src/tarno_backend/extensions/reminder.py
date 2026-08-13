"""Reminder engine for time- and condition-based user reminders."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)


@dataclass
class Reminder:
    id: str
    user_query: str
    trigger_time: datetime
    message: str
    acknowledged: bool = False


class ReminderEngine:
    """Stores reminders and notifies a callback when one is due."""

    def __init__(
        self,
        storage_path: Path | str = "~/.tarno/reminders.json",
        notify_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._path = Path(storage_path).expanduser()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._reminders: dict[str, Reminder] = {}
        self._notify = notify_callback or self._default_notify
        self._load()

    @staticmethod
    def _default_notify(message: str) -> None:
        log.info("Erinnerung: %s", message)

    def add(self, user_query: str, trigger_time: datetime, message: str) -> Reminder:
        reminder = Reminder(
            id=str(uuid.uuid4()),
            user_query=user_query,
            trigger_time=trigger_time,
            message=message,
        )
        self._reminders[reminder.id] = reminder
        self._save()
        log.info("Erinnerung erstellt: %s um %s", reminder.id, trigger_time)
        return reminder

    def acknowledge(self, reminder_id: str) -> bool:
        if reminder_id not in self._reminders:
            return False
        self._reminders[reminder_id].acknowledged = True
        self._save()
        return True

    def list_due(self, now: datetime | None = None) -> list[Reminder]:
        now = now or datetime.now()
        return [
            r for r in self._reminders.values()
            if not r.acknowledged and r.trigger_time <= now
        ]

    def check_and_notify(self) -> None:
        for reminder in self.list_due():
            self._notify(reminder.message)
            self.acknowledge(reminder.id)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            for item in raw:
                item["trigger_time"] = datetime.fromisoformat(item["trigger_time"])
                reminder = Reminder(**item)
                self._reminders[reminder.id] = reminder
        except Exception:
            log.exception("Erinnerungen konnten nicht geladen werden")

    def _save(self) -> None:
        data = [asdict(r) for r in self._reminders.values()]
        for item in data:
            item["trigger_time"] = item["trigger_time"].isoformat()
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
