"""Automatic fact extraction from user messages (Block 4, Phase 32).

Runs a lightweight, purely local regex-based extractor after each user
message - no extra LLM call per turn, consistent with Block 3's preference
for local heuristics over per-tick/per-turn model calls where reasonably
equivalent (see tarno/core/proactive_engine.py). This complements, but does
not replace, the LLM's own "remember_fact" tool, which it can call explicitly
when it recognizes something worth keeping that these patterns don't catch.
"""

from __future__ import annotations

import re

# Deliberately narrow, high-precision patterns over broad recall - a false
# "fact" (e.g. misparsing a throwaway remark as a permanent preference) is
# worse than occasionally missing one, since the LLM's own remember_fact tool
# call is the fallback for anything subtler.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # NOTE: "name"/"wohnort" deliberately do NOT use re.IGNORECASE - the
    # capture group's [A-ZÄÖÜ] leading-character class is what bounds the
    # proper noun (stops at the next lowercase word, e.g. "und"). Under
    # IGNORECASE, that class would match lowercase letters too, silently
    # defeating the boundary and swallowing trailing words (discovered via
    # live testing: "Ich heiße Jona und ich mag Pizza" extracted "Jona und"
    # instead of "Jona"). Case-insensitivity for the trigger phrase itself
    # is instead spelled out explicitly ([Ii]ch, [Hh]ei...).
    ("name", re.compile(
        r"\b[Ii]ch\s+[Hh]ei(?:ß|ss)e\s+([A-ZÄÖÜ][\wäöüß\-]+(?:\s+[A-ZÄÖÜ][\wäöüß\-]+)?)",
    )),
    ("wohnort", re.compile(
        r"\b[Ii]ch\s+[Ww]ohne\s+in\s+([A-ZÄÖÜ][\wäöüß\-]+)",
    )),
    ("lieblingsessen", re.compile(
        r"\bich\s+(?:mag|liebe)\s+([\wäöüß\- ]+?)(?:\s+am\s+liebsten|\s+sehr)?\s*[\.\!\?]",
        re.IGNORECASE,
    )),
    ("geburtstag", re.compile(
        r"\bmein\s+geburtstag\s+ist\s+(?:am\s+)?([\wäöüß0-9\.\- ]+?)[\.\!\?]",
        re.IGNORECASE,
    )),
]


class FactExtractor:
    """Extracts (key, value) fact candidates from a single user message."""

    def extract(self, user_text: str) -> list[tuple[str, str]]:
        facts: list[tuple[str, str]] = []
        for key, pattern in _PATTERNS:
            match = pattern.search(user_text)
            if not match:
                continue
            value = match.group(1).strip().rstrip(".!?")
            if value:
                facts.append((key, value))
        return facts
