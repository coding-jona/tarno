"""Small text helpers shared across TARNO."""

from __future__ import annotations

_EXIT_PHRASES = frozenset(
    ["exit", "beenden", "auf wiedersehen", "tschüss", "quit", "ende"]
)

_FAREWELL_PHRASES = (
    "auf wiedersehen",
    "es war mir ein vergnügen",
    "es war mir eine freude",
    "bis dann",
    "mach's gut",
    "tschüss",
    "ciao",
    "auf wiederseh'n",
    "goodbye",
    "bye",
)


def is_exit(text: str) -> bool:
    """Return True if the user text is a known exit/goodbye command."""
    lower = text.lower()
    words = lower.split()
    for phrase in _EXIT_PHRASES:
        if " " in phrase:
            if phrase in lower:
                return True
        elif phrase in words:
            return True
    return False


def contains_farewell(text: str) -> bool:
    """Return True if the text contains a farewell phrase."""
    lower = text.lower()
    return any(phrase in lower for phrase in _FAREWELL_PHRASES)
