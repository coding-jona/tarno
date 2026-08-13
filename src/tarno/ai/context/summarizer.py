"""Rekursiver Verlauf-Zusammenfasser mit dediziertem kleinen Modell
(Kontext-Effizienz Phase 4).

Nutzt ein eigenes, guenstiges Modell (ministral-3b-2512 bei Mistral) statt
des Haupt-Chat-Modells - direkt via create_provider() angefordert, NICHT
ueber den Denken-gated MistralDifficultyTiers-Pfad (der nur aktiv ist, wenn
"Denken" an UND difficulty_tiers.enabled=True ist - siehe dessen Docstring).

Rekursion: jeder summarize()-Aufruf bekommt die vorherige Zusammenfassung
als Eingabe und wird angewiesen, sie einzuschmelzen statt danebenzustellen -
die Ausgabe wird zum previous_summary des naechsten Aufrufs. So bleibt die
Laenge ueber viele Zyklen beschraenkt statt linear zu wachsen.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from tarno.ai.context.output_compressor import compress_tool_output
from tarno.ai.factory import create_provider
from tarno.ai.summarizer import ConversationSummarizer

if TYPE_CHECKING:
    from tarno.ai.provider import LLMProvider
    from tarno.core.config import TarnoConfig

log = logging.getLogger(__name__)

_RECURSIVE_SUMMARY_SYSTEM_PROMPT = (
    "Du bist ein spezialisiertes Zusammenfassungs-Modell. Du bekommst eine "
    "bereits komprimierte VORHERIGE Zusammenfassung sowie NEUE Nachrichten "
    "seit der letzten Zusammenfassung. Erzeuge EINE einzige, konsolidierte "
    "neue Zusammenfassung, die die vorherige Zusammenfassung EINSCHMILZT "
    "statt sie daneben zu stellen - wiederhole nichts doppelt. Behalte "
    "konkrete Fakten, Entscheidungen, Dateipfade und offene Aufgaben, die "
    "fuer die laufende Aufgabe noch relevant sind. Antworte ausschliesslich "
    "mit der neuen Zusammenfassung, in maximal etwa 300 Woertern."
)

_DEFAULT_SUMMARIZER_MODEL = "ministral-3b-2512"
_MAX_OUTPUT_CHARS = 2000


class HistorySummarizer:
    """Fasst Chat-Verlauf rekursiv zusammen - siehe Modul-Docstring."""

    def __init__(self, config: "TarnoConfig", provider: "LLMProvider | None" = None) -> None:
        self._provider = provider or self._build_default_provider(config)

    @staticmethod
    def _build_default_provider(config: "TarnoConfig") -> "LLMProvider":
        try:
            return create_provider(config, provider_name="mistral", model=_DEFAULT_SUMMARIZER_MODEL)
        except Exception:
            log.warning(
                "[CtxEff] Dediziertes Zusammenfassungs-Modell '%s' nicht verfügbar - "
                "weiche auf den konfigurierten Standard-Provider aus",
                _DEFAULT_SUMMARIZER_MODEL,
            )
            return create_provider(config)

    def summarize(self, messages: list[dict[str, Any]], previous_summary: str | None) -> str:
        prompt_parts: list[str] = []
        if previous_summary:
            prompt_parts.append(
                f"Vorherige Zusammenfassung (bereits komprimiert):\n{previous_summary}"
            )
        new_text = ConversationSummarizer._build_prompt(messages)
        prompt_parts.append(f"Neue Nachrichten seit letzter Zusammenfassung:\n{new_text}")
        prompt = "\n\n".join(prompt_parts)

        try:
            response = self._provider.send(
                messages=[{"role": "user", "content": prompt}],
                system=_RECURSIVE_SUMMARY_SYSTEM_PROMPT,
                tools=None,
            )
            summary = response.text.strip()
        except Exception:
            log.exception("[CtxEff] Rekursive Zusammenfassung fehlgeschlagen")
            summary = previous_summary or new_text

        if len(summary) > _MAX_OUTPUT_CHARS:
            summary = compress_tool_output(
                summary, tool_name="history_summary", max_chars=_MAX_OUTPUT_CHARS
            )
        return summary
