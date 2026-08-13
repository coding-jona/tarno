"""Post-processing that makes TARNO's spoken output sound more natural."""

from __future__ import annotations

import logging
import random
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tarno_backend.core.config import TTSPromptConfig

log = logging.getLogger(__name__)

_FILLERS = ["äh", "naja", "also", "hmm", "tja"]
_BACKCHANNELS = ["okay", "verstehe", "ich verstehe", "alles klar"]
_PROSODIC_BREAK = " ... "


class SpeechNaturalizer:
    """Lightweight text processor that adds human-like disfluencies and prosody.

    The LLM is already prompted to write spoken German, but this layer adds
    occasional fillers, short backchannel lead-ins and rhythmic pauses.
    """

    def __init__(
        self,
        filler_probability: float = 0.08,
        break_probability: float = 0.05,
        backchannel_probability: float = 0.03,
        max_fillers_per_message: int = 1,
        tts_prompt: "TTSPromptConfig | None" = None,
    ) -> None:
        self._filler_probability = filler_probability
        self._break_probability = break_probability
        self._backchannel_probability = backchannel_probability
        self._max_fillers = max_fillers_per_message
        self._tts_prompt = tts_prompt

    def _filler_pool(self) -> list[str]:
        if self._tts_prompt is not None and self._tts_prompt.filler_words:
            return list(self._tts_prompt.filler_words)
        return _FILLERS

    def _backchannel_pool(self) -> list[str]:
        if self._tts_prompt is not None and self._tts_prompt.connective_phrases:
            return list(self._tts_prompt.connective_phrases)
        return _BACKCHANNELS

    def enhance(self, text: str) -> str:
        """Return a slightly more natural version of *text* for TTS."""
        if not text or text.endswith("?"):
            return text

        fillers = self._filler_pool()
        backchannels = self._backchannel_pool()

        # Split into sentences to keep inserts local.
        sentences = re.split(r"(?<=[.!?])\s+", text)
        out: list[str] = []
        fillers_used = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Backchannel lead-in at the start of an answer.
            if not out and random.random() < self._backchannel_probability:
                sentence = f"{random.choice(backchannels)}, {sentence[0].lower()}{sentence[1:]}"

            # Inject a filler after the first few words of a longer sentence.
            if (
                fillers_used < self._max_fillers
                and len(sentence.split()) > 5
                and random.random() < self._filler_probability
            ):
                words = sentence.split()
                insert_after = min(2, len(words) - 1)
                words.insert(insert_after, random.choice(fillers))
                sentence = " ".join(words)
                fillers_used += 1

            # Add a prosodic pause after a comma or mid-sentence.
            if random.random() < self._break_probability and "," in sentence:
                sentence = sentence.replace(", ", _PROSODIC_BREAK, 1)

            out.append(sentence)

        return " ".join(out)

    def backchannel(self) -> str:
        """Return a short backchannel string (e.g. 'okay')."""
        return random.choice(self._backchannel_pool())
