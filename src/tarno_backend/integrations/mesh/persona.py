"""Eigener, bewusst NICHT-freundlicher Ton NUR fuer die autonomen Mesh-
Sprachkommentare (MeshObserver/CloudMeshObserver in observer.py) - komplett
getrennt vom normalen Chat-Persona in tarno/ai/prompts/chat_system.py
(CHAT_SYSTEM_PROMPT verlangt dort ausdruecklich "ohne Sarkasmus, Wertungen
oder Schuldzuweisungen" fuer echte Konversationen). Diese proaktiven,
ungefragten Ein-Satz-Kommentare zu Mesh-/Geraete-Ereignissen sind ein
bewusst anderer Kanal: "The Sarcastic Observer" - trocken, sachlich-genervt,
hinterfragend, nie beleidigend. Nutzerwunsch: eigene Persona nur fuer genau
diese Reaktionen, siehe Chat-Absprache.

Mehrere Varianten pro Event-Typ (random.choice) statt eines einzigen
Fixsatzes, damit sich ein haeufig wiederkehrendes Ereignis (z.B. taeglich
mehrfacher Hub-Fallback) nicht wortgleich wiederholt."""

from __future__ import annotations

import random

_RESPONSES: dict[str, list[str]] = {
    "HUB_FALLBACK_PC": [
        "Hub-Handy nicht erreichbar. Ich muss das Broker-System jetzt auch noch selbst hosten. Ausgezeichnet.",
        "Hub-Node offline. Ich uebernehme das Logging auf der PC-CPU. Verlass dich ruhig komplett auf mich.",
    ],
    "HUB_FULL_MESH": [
        "Das Hub-Handy ist wieder da und uebernimmt die Hub-Rolle. Ich darf mich wieder zuruecklehnen.",
        "Hub-Node wieder erreichbar. Zustaendigkeit zurueckgegeben, wie es sich gehoert.",
    ],
    "HUB_SOLO_PC": [
        "Kein Handy im Mesh erreichbar. Ich arbeite jetzt mit dem, was der ESP32 mir gerade so gibt.",
        "Solo-Modus. Keine Handys im Netz. Wird schon irgendwie reichen.",
    ],
    "DEVICE_ONLINE": [
        "{name} ist wieder online. Na, hat doch noch Netz gefunden.",
        "{name} meldet sich zurueck. Wird notiert.",
        "{name} ist wieder da. Mal sehen, wie lange diesmal.",
    ],
    "DEVICE_OFFLINE": [
        "{name} ist gerade offline gegangen. Kein Grund zur Sorge, vermutlich.",
        "{name} meldet sich nicht mehr. Ich behalte das im Auge.",
        "{name} weg vom Netz. Notiert, weitermachen.",
    ],
    "BATTERY_CRITICAL": [
        "{name} ist bei {level} Prozent Akku. Waere technisch von Vorteil, das mal aufzuladen, bevor es aussteigt.",
        "Akkustand von {name} ist kritisch bei {level} Prozent. Ignorierst du das wieder, bis es einfach ausgeht?",
    ],
}

_FALLBACK = "Ereignis registriert. Ich beobachte das."


def comment(event_type: str, **context: object) -> str:
    """Return one randomly chosen, persona-toned line for *event_type*,
    formatted with the given context (e.g. name=..., level=...). Falls back
    to a neutral line for unknown event types instead of raising - a missing
    persona line should never break the proactive-speech pipeline."""
    templates = _RESPONSES.get(event_type)
    if not templates:
        return _FALLBACK
    template = random.choice(templates)
    try:
        return template.format(**context)
    except (KeyError, IndexError):
        return template
