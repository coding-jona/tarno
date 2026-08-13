"""Conversation summarization to keep long TARNO chats within the context window."""

from __future__ import annotations

import logging
from typing import Any

from tarno.ai.conversation import ConversationManager
from tarno.ai.provider import LLMProvider

log = logging.getLogger(__name__)

_SUMMARY_SYSTEM_PROMPT = (
    "Erstelle eine knappe Zusammenfassung der folgenden Konversation. "
    "Behalte alle wichtigen Fakten, Entscheidungen und offenen Aufgaben bei. "
    "Antworte ausschließlich mit der Zusammenfassung."
)


class ConversationSummarizer:
    """Monitors conversation length and replaces older turns with a summary."""

    def __init__(
        self,
        provider: LLMProvider,
        threshold: int = 18,
        keep_last: int = 5,
    ) -> None:
        self._provider = provider
        self._threshold = threshold
        self._keep_last = keep_last

    def maybe_summarize(self, conversation: ConversationManager) -> bool:
        """Summarize older messages if the conversation exceeds the threshold.

        Returns True if a summary was created.
        """
        messages = conversation.get_messages()
        if len(messages) < self._threshold:
            return False

        older = messages[: -self._keep_last]
        summary = self._summarize(older)
        conversation.replace_with_summary(summary, keep_last=self._keep_last)
        log.info(
            "Konversation zusammengefasst (%d -> %d Nachrichten)",
            len(messages),
            self._keep_last + 1,
        )
        return True

    def _summarize(self, messages: list[dict[str, Any]]) -> str:
        prompt = self._build_prompt(messages)
        try:
            response = self._provider.send(
                messages=[{"role": "user", "content": prompt}],
                system=_SUMMARY_SYSTEM_PROMPT,
                tools=None,
            )
            return response.text.strip()
        except Exception:
            log.exception("Zusammenfassung fehlgeschlagen")
            return self._fallback_summary(messages)

    @staticmethod
    def _build_prompt(messages: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, list):
                text = " ".join(
                    str(block.get("text", block)) for block in content
                )
            else:
                text = str(content)
            lines.append(f"{role}: {text}")
        return "\n".join(lines)

    @staticmethod
    def _fallback_summary(messages: list[dict[str, Any]]) -> str:
        """If the LLM fails, keep the most recent user and assistant texts."""
        snippets = []
        for msg in messages:
            if msg.get("role") in ("user", "assistant"):
                content = msg.get("content", "")
                if isinstance(content, str):
                    snippets.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and "text" in block:
                            snippets.append(block["text"])
        return "\n".join(snippets[-10:])
