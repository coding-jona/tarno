"""Shared protocol for coding-agent adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Protocol, runtime_checkable


@dataclass(frozen=True)
class CodingOutput:
    """One item emitted by a coding backend while a task is running.

    Attributes:
        kind: Output category, e.g. "text", "diff", "error", "summary".
        text: Human-readable content for this item.
        timestamp_ms: Monotonic millisecond when the item was produced.
        meta: Optional structured metadata (path, exit code, model name, ...).
    """

    kind: str
    text: str
    timestamp_ms: int = 0
    meta: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class CodingBackend(Protocol):
    """Contract that every coding adapter must satisfy.

    Kept in sync with the ABC in adapters/base.py (which is what dispatcher.py
    actually type-hints against and every concrete backend subclasses) - this
    Protocol had drifted out of sync (missing on_output) until a code review
    caught it; both must match, since either could plausibly be the one a new
    caller type-checks against."""

    def run(
        self,
        prompt: str,
        workspace: dict[str, Any],
        fnames: list[str],
        read_only: bool,
        on_output: Callable[[CodingOutput], None] | None = None,
    ) -> Iterator[CodingOutput]:
        """Execute a coding task and yield progress/output items.

        Args:
            prompt: The user's request in natural language.
            workspace: Active workspace descriptor (folders, includes, excludes).
            fnames: List of absolute file paths to consider as context.
            read_only: If True, the adapter must not modify files.
            on_output: Optional callback invoked for every item as it's produced,
                so callers can stream progress before the generator finishes.
        """
        ...
