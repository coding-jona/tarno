"""Audit logger for voice actions, permissions and audio state changes."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


class VoiceAuditLogger:
    """Append-only text logger for voice-related events."""

    def __init__(self, log_dir: Path | str = "~/.tarno/logs") -> None:
        self._log_dir = Path(log_dir).expanduser()
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self._log_dir / "voice_audit.log"

    def log_permission_request(
        self,
        permission: str,
        target: str,
        user_query: str,
    ) -> None:
        self._write(
            event="PERMISSION_REQUEST",
            permission=permission,
            target=target,
            user_query=user_query,
        )

    def log_permission_grant(
        self,
        permission: str,
        target: str,
        duration_seconds: float | None,
        persistent: bool,
    ) -> None:
        self._write(
            event="PERMISSION_GRANTED",
            permission=permission,
            target=target,
            duration=duration_seconds,
            persistent=persistent,
        )

    def log_permission_revoke(self, permission: str, target: str) -> None:
        self._write(
            event="PERMISSION_REVOKED",
            permission=permission,
            target=target,
        )

    def log_tts_state(self, state: str) -> None:
        self._write(event="TTS_STATE", state=state)

    def log_recording(self, action: str, purpose: str, path: str) -> None:
        self._write(
            event="RECORDING",
            action=action,
            purpose=purpose,
            path=path,
        )

    def log_external_output(self, action: str, target: str, success: bool) -> None:
        self._write(
            event="EXTERNAL_OUTPUT",
            action=action,
            target=target,
            success=success,
        )

    def _write(self, event: str, **kwargs: Any) -> None:
        timestamp = datetime.now().isoformat(sep=" ", timespec="seconds")
        details = " ".join(f"{k}={v}" for k, v in kwargs.items())
        line = f"{timestamp} [{event}] {details}\n"
        with open(self._log_file, "a", encoding="utf-8") as f:
            f.write(line)
