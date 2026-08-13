"""Tests for tarno/ai/context/summarizer.py (Kontext-Effizienz Phase 4)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from tarno_backend.ai.context.summarizer import HistorySummarizer


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class HistorySummarizerTests(unittest.TestCase):
    def test_first_call_has_no_previous_summary_in_prompt(self) -> None:
        provider = MagicMock()
        provider.send.return_value = _FakeResponse("Erste Zusammenfassung")
        summarizer = HistorySummarizer.__new__(HistorySummarizer)
        summarizer._provider = provider

        result = summarizer.summarize(
            [{"role": "user", "content": "hallo"}], previous_summary=None
        )

        self.assertEqual(result, "Erste Zusammenfassung")
        sent_prompt = provider.send.call_args.kwargs["messages"][0]["content"]
        self.assertNotIn("Vorherige Zusammenfassung", sent_prompt)
        self.assertIn("Neue Nachrichten", sent_prompt)

    def test_recursive_call_includes_previous_summary_in_prompt(self) -> None:
        provider = MagicMock()
        provider.send.return_value = _FakeResponse("Zweite, eingeschmolzene Zusammenfassung")
        summarizer = HistorySummarizer.__new__(HistorySummarizer)
        summarizer._provider = provider

        result = summarizer.summarize(
            [{"role": "user", "content": "weiter"}],
            previous_summary="Erste Zusammenfassung",
        )

        self.assertEqual(result, "Zweite, eingeschmolzene Zusammenfassung")
        sent_prompt = provider.send.call_args.kwargs["messages"][0]["content"]
        self.assertIn("Vorherige Zusammenfassung", sent_prompt)
        self.assertIn("Erste Zusammenfassung", sent_prompt)

    def test_provider_failure_falls_back_to_previous_summary(self) -> None:
        provider = MagicMock()
        provider.send.side_effect = RuntimeError("API down")
        summarizer = HistorySummarizer.__new__(HistorySummarizer)
        summarizer._provider = provider

        result = summarizer.summarize(
            [{"role": "user", "content": "x"}], previous_summary="Letzter guter Stand"
        )

        self.assertEqual(result, "Letzter guter Stand")

    def test_overlong_summary_is_truncated(self) -> None:
        provider = MagicMock()
        provider.send.return_value = _FakeResponse("x" * 5000)
        summarizer = HistorySummarizer.__new__(HistorySummarizer)
        summarizer._provider = provider

        result = summarizer.summarize([{"role": "user", "content": "x"}], previous_summary=None)

        self.assertLessEqual(len(result), 2000)


if __name__ == "__main__":
    unittest.main()
