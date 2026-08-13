"""Centralised structured logging with correlation IDs for TARNO."""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import uuid
from pathlib import Path
from typing import Any

from tarno.security.pii import redact as redact_pii

# Unique correlation ID for the current session / turn.
_CORRELATION_ID = contextvars.ContextVar("correlation_id", default=None)


class CorrelationIdFilter(logging.Filter):
    """Injects the current correlation ID into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        cid = _CORRELATION_ID.get()
        record.correlation_id = cid if cid else "no-cid"
        return True


class PiiRedactionFilter(logging.Filter):
    """Redacts PII from log messages before formatting."""

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "pii_redacted", False):
            return True
        record.msg = redact_pii(record.getMessage())
        record.args = ()
        record.pii_redacted = True
        return True


class StructuredFormatter(logging.Formatter):
    """Human readable formatter including correlation ID."""

    def __init__(self, fmt: str | None = None) -> None:
        super().__init__(fmt)

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        if self.usesTime():
            record.asctime = self.formatTime(record, self.datefmt)
        cid = getattr(record, "correlation_id", "no-cid")
        msg = f"{record.asctime} [{record.levelname}] [cid={cid}] {record.name}: {record.message}"
        if record.exc_info:
            msg += "\n" + self.formatException(record.exc_info)
        return msg


class JsonFormatter(logging.Formatter):
    """JSON formatter for machine-readable log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt) if self.usesTime() else record.created,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", "no-cid"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(
    level: str = "INFO",
    json_format: bool = False,
    log_file: Path | None = None,
    redact_pii: bool = False,
) -> None:
    """Configure the root logger for TARNO.

    Existing handlers are replaced so the configuration is deterministic across
    entry points (CLI, GUI, tests).
    """
    # Windows console streams default to the legacy codepage (cp1252 etc.),
    # which raises UnicodeEncodeError on emoji/non-Latin1 characters that LLM
    # responses routinely contain (found live: crashed the ResponseReadyEvent
    # handler and the TTS log line on a plain "😊" in the reply). Reconfigure
    # to UTF-8 with replacement so logging/print never crashes on content,
    # regardless of the end user's system codepage - not just cp1252.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.addFilter(CorrelationIdFilter())
    if redact_pii:
        stream_handler.addFilter(PiiRedactionFilter())

    if json_format:
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = StructuredFormatter("%(asctime)s")
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.addFilter(CorrelationIdFilter())
        if redact_pii:
            file_handler.addFilter(PiiRedactionFilter())
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a logger that participates in the TARNO logging setup."""
    return logging.getLogger(name)


def set_correlation_id(cid: str | None) -> None:
    """Set the correlation ID for the current context (session / turn)."""
    _CORRELATION_ID.set(cid)


def get_correlation_id() -> str | None:
    """Return the current correlation ID, if any."""
    return _CORRELATION_ID.get()


def new_correlation_id() -> str:
    """Generate a new unique correlation ID."""
    return str(uuid.uuid4())
