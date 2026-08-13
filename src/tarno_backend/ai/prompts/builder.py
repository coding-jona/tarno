"""Build layered system prompts for TARNO.

Inspired by claude-code-main/src/utils/systemPrompt.ts:
override -> coordinator -> agent -> custom -> default -> append.
"""

from __future__ import annotations

from datetime import datetime

from tarno_backend.ai.prompts.chat_system import CHAT_SYSTEM_PROMPT
from tarno_backend.ai.prompts.code_system import CODE_SYSTEM_PROMPT, build_workspace_prompt
from tarno_backend.ai.prompts.tts_voice_prompt import build_tts_prompt
from tarno_backend.core.config import TTSPromptConfig

_VALID_MODES = frozenset({"chat", "code"})


def _datetime_prompt() -> str:
    """Return a German date/time string and ground-truth instructions."""
    now = datetime.now()
    weekdays = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    formatted = f"{weekdays[now.weekday()]}, {now:%d.%m.%Y %H:%M} Uhr"
    return (
        f"\n\nAktuelles Datum und Uhrzeit: {formatted}. Verlasse dich "
        "IMMER auf diesen Wert für 'heute'/'jetzt' - insbesondere beim Zusammenfassen "
        "von Tool-Ergebnissen (z.B. add_reminder): gib Datum/Uhrzeit aus dem "
        "tatsächlichen Tool-Ergebnis wortgetreu wieder, erfinde niemals ein eigenes.\n\n"
        "GROUND TRUTH: Der Inhalt jedes Tool-Ergebnisses "
        "(insbesondere von Kamerasensoren/describe_what_i_see) ist die maßgebliche Quelle. "
        "Verwende ausschließlich Informationen, die explizit im Tool-Resultat stehen. "
        "Vermeide Ausschmückungen, Vermutungen oder erfundene Details (z.B. Objekte, "
        "Körperhaltung, Lichtverhältnisse), die nicht im Tool-Bericht genannt wurden. "
        "Wenn das Tool ein Detail nicht nennt, existiert es für dich nicht.\n\n"
        "TOOL-ERGEBNISSE SIND ROHDATEN, KEINE ANTWORT: Ein Tool-Ergebnis (z.B. eine "
        "Verzeichnisliste) darfst du NIEMALS wortgetreu als deine Antwort ausgeben - "
        "interpretiere es immer und formuliere die Antwort in deiner eigenen Stimme. Und "
        "bevor du ein Datei-/Verzeichnis-Tool aufrufst: prüfe, ob die Frage sich wirklich "
        "auf echte Computerdateien bezieht. Fragen zu physischen, realen Dingen (z.B. "
        "'was habe ich im Kühlschrank', 'was liegt auf meinem Schreibtisch') sind KEINE "
        "Dateisystem-Anfragen - erkläre ehrlich, dass du keinen Zugriff auf die "
        "physische Welt hast, statt stattdessen einen Ordner deines eigenen Systems "
        "aufzulisten."
    )


def build_system_prompt(
    mode: str,
    workspace: dict[str, object] | None = None,
    custom: str | None = None,
    append: str | None = None,
    tts_config: TTSPromptConfig | None = None,
) -> str:
    """Return a layered system prompt for the given mode.

    Args:
        mode: "chat" or "code".
        workspace: Optional active workspace dict (used in code mode).
        custom: Optional custom system prompt that replaces the default section.
        append: Optional text appended at the very end.

    Returns:
        The assembled system prompt string.
    """
    if mode not in _VALID_MODES:
        mode = "chat"

    parts: list[str] = []

    if custom:
        parts.append(custom)
    elif mode == "code":
        parts.append(CODE_SYSTEM_PROMPT)
    else:
        parts.append(CHAT_SYSTEM_PROMPT)

    parts.append(_datetime_prompt())

    if mode == "chat" and tts_config is not None and tts_config.enabled:
        tts_prompt = build_tts_prompt(tts_config)
        if tts_prompt:
            parts.append("\n\n")
            parts.append(tts_prompt)

    if mode == "code":
        parts.append(build_workspace_prompt(workspace))

    if append:
        parts.append(f"\n\n{append}")

    return "".join(parts)
