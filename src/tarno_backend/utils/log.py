"""Logging setup facade that delegates to tarno.telemetry.logging."""

from __future__ import annotations

from pathlib import Path

from tarno_backend.telemetry.logging import configure_logging


def setup_logging(
    level: str = "INFO",
    log_file: Path | None = None,
    redact_pii: bool = False,
) -> None:
    """Configure TARNO logging with structured output and correlation IDs."""
    configure_logging(level=level, log_file=log_file, redact_pii=redact_pii)
