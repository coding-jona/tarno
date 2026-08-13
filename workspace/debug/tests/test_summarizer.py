"""Tests for conversation summarization."""

from __future__ import annotations

import unittest
from typing import Any

from tarno.ai.conversation import ConversationManager
from tarno.ai.provider import LLMProvider, LLMResponse
from tarno.ai.summarizer import ConversationSummarizer


class FakeProvider(LLMProvider):
    """Provider that returns a deterministic summary."""

    def __init__(self, summary: str) -> None:
        self._summary = summary

    @property
    def name(self) -> str:
        return "fake"

    @property
    def supports_tools(self) -> bool:
        return False

    def send(self, messages, system, tools=None) -> LLMResponse:
        return LLMResponse(text=self._summary, tool_calls=[])

    def send_tool_result(self, messages, system, tools=None) -> LLMResponse:
        return LLMResponse(text="", tool_calls=[])


class ConversationSummarizerTests(unittest.TestCase):
    """Unit tests for ConversationSummarizer."""

    def test_no_summary_below_threshold(self):
        provider = FakeProvider("summary")
        summarizer = ConversationSummarizer(provider, threshold=10, keep_last=2)
        conversation = ConversationManager(max_history=20)
        for i in range(3):
            conversation.add_user_message(f"Msg {i}")
            conversation.add_assistant_response(f"Reply {i}")
        self.assertFalse(summarizer.maybe_summarize(conversation))

    def test_summary_reduces_history(self):
        provider = FakeProvider("Die Nutzer wollten Tests.")
        summarizer = ConversationSummarizer(provider, threshold=6, keep_last=2)
        conversation = ConversationManager(max_history=20)
        for i in range(5):
            conversation.add_user_message(f"Nutzer {i}")
            conversation.add_assistant_response(f"Assistant {i}")
        # 10 messages, threshold 6 -> should summarize.
        self.assertTrue(summarizer.maybe_summarize(conversation))
        messages = conversation.get_messages()
        self.assertEqual(len(messages), 3)  # summary + 2 recent turns
        self.assertIn("Zusammenfassung", messages[0]["content"])


if __name__ == "__main__":
    unittest.main()
