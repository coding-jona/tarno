"""User preference learning from explicit statements and repeated patterns."""

from __future__ import annotations

import logging
from typing import Any

from tarno.memory.store import MemoryStore

log = logging.getLogger(__name__)


class PreferenceManager:
    """Tracks user preferences and updates confidence as patterns repeat."""

    _POSITIVE_HINTS = ["immer", "bevorzuge", "gerne", "möchte", "mag ich"]
    _NEGATIVE_HINTS = ["nie", "nicht", "hasse", "abneigung"]

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def record_explicit(
        self,
        key: str,
        value: str,
        confidence: float = 0.9,
    ) -> None:
        """Store an explicitly stated preference."""
        self._store.set_preference(key, value, confidence)
        log.info("Präferenz gespeichert: %s = %s", key, value)

    def infer_from_utterance(self, user_text: str) -> list[dict[str, Any]]:
        """Infer preference updates from a user message.

        Returns a list of detected preferences without writing them, so the
        caller can confirm high-confidence inferences.
        """
        lower = user_text.lower()
        polarity = 0.5
        if any(h in lower for h in self._POSITIVE_HINTS):
            polarity = 0.9
        elif any(h in lower for h in self._NEGATIVE_HINTS):
            polarity = 0.1

        # Simple keyword extraction for music/app preferences.
        candidates = []
        for marker, category in [("höre", "music"), ("nutze", "app"), ("öffne", "app")]:
            if marker in lower:
                # Naive extraction: word after marker.
                parts = lower.split()
                if marker in parts:
                    idx = parts.index(marker)
                    if idx + 1 < len(parts):
                        value = parts[idx + 1]
                        candidates.append({
                            "key": f"{category}_preference",
                            "value": value,
                            "confidence": polarity,
                        })
        return candidates

    def get(self, key: str) -> dict[str, Any] | None:
        return self._store.get_preference(key)
