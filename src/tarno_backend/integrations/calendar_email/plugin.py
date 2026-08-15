"""TARNO plugin for calendar and email access."""

from __future__ import annotations

from typing import Any

from tarno_backend.ai.tool_registry import ToolDefinition
from tarno_backend.core.action_result import ActionResult
from tarno_backend.integrations.calendar_email.client import CalendarClient, EmailClient
from tarno_backend.plugins.base import BasePlugin


class CalendarEmailPlugin(BasePlugin):
    """Provides read-only access to calendar events and email counts."""

    name = "calendar_email"
    version = "1.0.0"
    dependencies: list[str] = []

    def __init__(self) -> None:
        super().__init__()
        self._calendar: CalendarClient | None = None
        self._email: EmailClient | None = None

    def on_load(self) -> None:
        config = self._context.get("config") if self._context else {}
        if isinstance(config, dict):
            if config.get("calendar_file"):
                self._calendar = CalendarClient(config["calendar_file"])
            email_cfg = config.get("email")
            if isinstance(email_cfg, dict):
                self._email = EmailClient(
                    host=email_cfg.get("host", "imap.example.com"),
                    username=email_cfg.get("username", ""),
                    password=email_cfg.get("password", ""),
                    port=email_cfg.get("port", 993),
                )
        self.audit("loaded", {})

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="calendar_today",
                description="Listet heutige und kommende Kalendertermine.",
                input_schema={
                    "type": "object",
                    "properties": {"days": {"type": "integer", "default": 1}},
                },
                handler=self._calendar_today,
            ),
            ToolDefinition(
                name="email_unread",
                description="Gibt die Anzahl ungelesener E-Mails zurück.",
                input_schema={"type": "object", "properties": {}},
                handler=self._email_unread,
            ),
        ]

    def _calendar_today(self, days: int = 1) -> ActionResult:
        if self._calendar is None:
            return self.failure("Kein Kalender konfiguriert", error_code="NotConfigured")
        events = self._calendar.list_events(days=days)
        if not events:
            return self.success("Keine anstehenden Termine.")
        lines = [
            f"{e.start.strftime('%d.%m. %H:%M')}: {e.summary}"
            for e in events
        ]
        return self.success("\n".join(lines))

    def _email_unread(self) -> ActionResult:
        if self._email is None:
            return self.failure("Kein E-Mail-Konto konfiguriert", error_code="NotConfigured")
        count = self._email.unread_count()
        return self.success(f"{count} ungelesene E-Mails.", details={"count": count})


def create_plugin(_manifest: dict[str, Any]) -> CalendarEmailPlugin:
    """Entry point PluginManager calls to instantiate this plugin."""
    return CalendarEmailPlugin()
