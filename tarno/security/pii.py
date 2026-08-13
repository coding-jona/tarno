"""PII redaction helpers for logs and LLM context."""

from __future__ import annotations

import re
from typing import Any


# Regex patterns for common PII.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")),
    ("phone", re.compile(r"(?:\+\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}")),
    ("credit_card", re.compile(r"\b(?:\d[ -]*?){13,16}\b")),
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}[\s]?[A-Z0-9]{4}[\s]?[0-9]{7}(?:[\s]?[A-Z0-9]{1,16})?\b")),
    # Bearer-Token in Authorization-Headern (z.B. versehentlich geloggte
    # Request-Header): "Bearer sk-abc123..." -> "Bearer [REDACTED]"
    ("bearer_token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-_.=]{16,}")),
    # key=value / key: value Zuweisungen fuer typische Secret-Namen im
    # Freitext (z.B. in Debug-Strings oder Exception-Messages).
    ("secret_assignment", re.compile(
        r"(?i)\b(api[_-]?key|access[_-]?token|secret|password|master[_-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9\-_.]{8,}['\"]?"
    )),
]


def redact(text: str, replace_with: str = "[REDACTED]") -> str:
    """Replace common PII patterns in *text* with *replace_with*."""
    redacted = text
    for _label, pattern in _PATTERNS:
        redacted = pattern.sub(replace_with, redacted)
    return redacted


def redact_dict(data: dict[str, Any], sensitive_keys: set[str] | None = None) -> dict[str, Any]:
    """Return a copy of *data* with sensitive keys redacted."""
    keys = sensitive_keys or {
        "api_key",
        "password",
        "token",
        "secret",
        "master_key",
        "credit_card",
        "iban",
    }
    result: dict[str, Any] = {}
    for key, value in data.items():
        if key.lower() in keys:
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = redact_dict(value, keys)
        elif isinstance(value, str):
            result[key] = redact(value)
        else:
            result[key] = value
    return result


def is_likely_pii(text: str) -> bool:
    """Return True if *text* appears to contain PII."""
    for _label, pattern in _PATTERNS:
        if pattern.search(text):
            return True
    return False
