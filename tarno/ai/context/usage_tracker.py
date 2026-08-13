"""Kontext-Nutzungs-Tracker (Kontext-Effizienz Phase 3).

Verfolgt, wie voll der Kontext eines Providers ist, um rekursive
Zusammenfassung (siehe summarizer.py) bei ~75% Auslastung auszuloesen.
Nicht jeder Provider/Turn meldet tokens_used/context_window (siehe
LLMResponse-Docstring) - die Ratio ist deshalb sticky (behaelt den letzten
echten Wert) und faellt bei fehlenden Daten auf einen Zeichen-basierten
Schaetzer zurueck, statt einzufrieren oder None zu liefern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ~4 Zeichen pro Token ist eine grobe, aber verbreitete Faustregel fuer
# englisch-/deutschsprachigen Text - nur ein Fallback, wenn kein Provider
# echte Nutzungsdaten fuer diesen Turn geliefert hat.
_CHARS_PER_TOKEN_ESTIMATE = 4
_DEFAULT_CONTEXT_WINDOW_ESTIMATE = 32_000

SUMMARIZE_THRESHOLD_RATIO = 0.75
_DEFAULT_COOLDOWN_MESSAGES = 4


@dataclass
class ContextUsageTracker:
    """Eine Instanz pro ConversationManager/Pool-Agent."""

    threshold_ratio: float = SUMMARIZE_THRESHOLD_RATIO
    cooldown_messages: int = _DEFAULT_COOLDOWN_MESSAGES
    default_context_window: int = _DEFAULT_CONTEXT_WINDOW_ESTIMATE

    last_known_ratio: float | None = field(default=None, init=False)
    _last_was_estimate: bool = field(default=False, init=False)
    _messages_since_last_summary: int = field(default=0, init=False)

    def record(self, tokens_used: int | None, context_window: int | None) -> None:
        """Vom Provider gemeldete Nutzung - ueberschreibt jeden Schaetzwert."""
        self._messages_since_last_summary += 1
        if tokens_used is None or context_window is None or context_window <= 0:
            return
        self.last_known_ratio = tokens_used / context_window
        self._last_was_estimate = False

    def record_estimate(self, messages: list[dict[str, Any]], context_window: int | None = None) -> None:
        """Zeichen-basierter Fallback-Schaetzer fuer Turns/Provider ohne
        gemeldete Nutzung - haelt das Signal am Leben statt einzufrieren."""
        window = context_window or self.default_context_window
        total_chars = sum(len(_flatten_content(msg.get("content", ""))) for msg in messages)
        estimated_tokens = total_chars // _CHARS_PER_TOKEN_ESTIMATE
        self.last_known_ratio = estimated_tokens / window if window > 0 else None
        self._last_was_estimate = True

    @property
    def last_ratio_is_estimate(self) -> bool:
        return self._last_was_estimate

    def should_summarize(self) -> bool:
        if self.last_known_ratio is None:
            return False
        if self.last_known_ratio < self.threshold_ratio:
            return False
        return self._messages_since_last_summary >= self.cooldown_messages

    def reset_after_summary(self) -> None:
        self._messages_since_last_summary = 0


def _flatten_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text", block.get("content", ""))))
            else:
                parts.append(str(block))
        return " ".join(parts)
    return str(content)
