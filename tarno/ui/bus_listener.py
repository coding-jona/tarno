"""UI-side listener for the OVOS message bus."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal
from ovos_bus_client import MessageBusClient
from ovos_bus_client.message import Message

log = logging.getLogger(__name__)


class BusListener(QObject):
    """Connects to the OVOS bus and forwards events to the UI via Qt signals."""

    assistant_message = Signal(str)
    status_changed = Signal(str)
    log_message = Signal(str)
    error_occurred = Signal(str)
    task_approval_requested = Signal(str, str)  # task_id, description

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._client: MessageBusClient | None = None

    def start(self) -> None:
        self._client = MessageBusClient()
        self._client.on("speak", self._on_speak)
        self._client.on("tarno.status", self._on_status)
        self._client.on("tarno.error", self._on_error)
        self._client.on("tarno.task.approval.request", self._on_task_approval_request)
        self._client.run_in_thread()

    def stop(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def _on_speak(self, message: Message) -> None:
        text = message.data.get("utterance", "")
        if text:
            self.assistant_message.emit(text)

    def _on_status(self, message: Message) -> None:
        state = message.data.get("state", "")
        if state:
            self.status_changed.emit(state)

    def _on_error(self, message: Message) -> None:
        text = message.data.get("message", "")
        if text:
            self.error_occurred.emit(text)

    def _on_task_approval_request(self, message: Message) -> None:
        task_id = message.data.get("task_id", "")
        description = message.data.get("description", "")
        if task_id:
            self.task_approval_requested.emit(task_id, description)

    def send_task_approval(self, task_id: str, approved: bool) -> None:
        if self._client is None:
            return
        msg_type = "tarno.task.approval.grant" if approved else "tarno.task.approval.deny"
        self._client.emit(Message(msg_type, data={"task_id": task_id}))
