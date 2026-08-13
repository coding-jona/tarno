"""Command action audit logger for TARNO."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from tarno_backend.core.action_result import ActionResult

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


@dataclass
class ActionLogEntry:
    timestamp: str
    user_query: str
    intent: str
    shell: str
    command: str
    risk_level: str
    success: bool
    error_code: str | None
    output_summary: str


class ActionLogger:
    """Append-only text logger for executed commands."""

    def __init__(self, log_dir: Path | str = "~/.tarno/logs") -> None:
        self._log_dir = Path(log_dir).expanduser()
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self._log_dir / "action.log"

    def log(
        self,
        user_query: str,
        intent: str,
        shell: str,
        command: str,
        risk_level: str,
        result: ActionResult,
    ) -> None:
        entry = self._format_entry(
            ActionLogEntry(
                timestamp=_now(),
                user_query=user_query,
                intent=intent,
                shell=shell,
                command=command,
                risk_level=risk_level,
                success=result.success,
                error_code=result.error_code,
                output_summary=self._summarize(result.message),
            )
        )
        with open(self._log_file, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
            f.write("-" * 60 + "\n")

        # Also emit through `logging` so this entry reaches every consumer
        # already wired to the standard logging pipeline - notably the gRPC
        # bridge's _BridgeLogHandler, which streams INFO+ records to the
        # WinUI Logs panel. Without this, executed commands were written to
        # action.log on disk but never visible anywhere in the UI, even
        # though Phase 4 explicitly calls for an audit log with UI
        # integration ("Audit-Log zeigt alle ausgeführten Commands").
        summary = f"[{risk_level.upper()}] {intent}: {command} -> {'OK' if result.success else 'FEHLER'}"
        if result.success:
            log.info(summary)
        else:
            log.warning(summary)

    @staticmethod
    def _format_entry(entry: ActionLogEntry) -> str:
        return (
            f"{entry.timestamp} [INTENT: {entry.intent}] [RISK: {entry.risk_level}] [SHELL: {entry.shell}]\n"
            f"  User: {entry.user_query}\n"
            f"  Command: {entry.command}\n"
            f"  Status: {'SUCCESS' if entry.success else 'FAILED'}"
            f"{f' ({entry.error_code})' if entry.error_code else ''}\n"
            f"  Output: {entry.output_summary}"
        )

    @staticmethod
    def _summarize(text: str, max_len: int = 500) -> str:
        text = text.strip().replace("\n", " ")
        if len(text) <= max_len:
            return text
        return text[:max_len] + "..."


def get_action_logger(config_value: Any = None) -> ActionLogger:
    """Factory that accepts a config object, dict or path string."""
    if config_value is None:
        return ActionLogger()
    if isinstance(config_value, (str, Path)):
        return ActionLogger(config_value)
    # Assume dataclass / object with a log_dir attribute.
    log_dir = getattr(config_value, "log_dir", "~/.tarno/logs")
    return ActionLogger(log_dir)
