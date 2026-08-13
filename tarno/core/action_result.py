"""Standard result contract shared by tools, commands and external actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ActionResult:
    """Immutable result of an executed action.

    Attributes:
        success: True if the action completed as intended.
        message: Human-readable summary of the outcome.
        error_code: Optional machine-readable error category.
        details: Optional structured data (e.g. returncode, stdout, stderr).
        attachment: Optional binary payload (e.g. JPEG frame for vision tools).
    """

    success: bool
    message: str
    error_code: str | None = None
    details: dict[str, Any] | None = None
    attachment: bytes | None = None

    def __str__(self) -> str:
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "success": self.success,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details,
        }

    @classmethod
    def from_exception(cls, exc: Exception, message: str | None = None) -> "ActionResult":
        """Create a failed result from an exception."""
        return cls(
            success=False,
            message=message or f"Fehler: {exc}",
            error_code=type(exc).__name__,
            details={"exception": str(exc)},
        )
