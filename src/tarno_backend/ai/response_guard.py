"""Guard assistant responses to avoid unwanted farewells."""

from __future__ import annotations

from tarno_backend.utils.text import contains_farewell, is_exit


_FAREWELL_REPLACEMENT = (
    "Entschuldigung, Sir. Ich kann diese Anfrage nicht direkt umsetzen. "
    "Soll ich eine Alternative vorschlagen oder die Aufgabe anders angehen?"
)


def guard_response(text: str, user_text: str) -> str:
    """Return a safe response if the assistant accidentally says goodbye.

    If the user explicitly said goodbye, farewells are allowed. Otherwise a
    detected farewell is replaced with a polite clarification offer.
    """
    if not text:
        return text

    if is_exit(user_text):
        return text

    if contains_farewell(text):
        return _FAREWELL_REPLACEMENT

    return text
