"""Regression test: ConversationManager.system_prompt must always include
the real current date/time (found via live testing - without this, the
model had no ground truth for "today" and hallucinated a wrong date twice
in a row when summarizing an add_reminder tool call, even though the tool
itself stored the correct date both times)."""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch

from tarno.ai.conversation import ConversationManager


class SystemPromptDateInjectionTests(unittest.TestCase):
    def test_system_prompt_contains_current_date(self) -> None:
        cm = ConversationManager()
        today_str = f"{datetime.now():%d.%m.%Y}"
        self.assertIn(today_str, cm.system_prompt)

    def test_system_prompt_is_read_only(self) -> None:
        cm = ConversationManager()
        with self.assertRaises(AttributeError):
            cm.system_prompt = "override"  # type: ignore[misc]

    def test_system_prompt_reflects_a_later_access_time(self) -> None:
        """Since system_prompt is computed fresh on every access (matching
        the fact that it's resent in full on every single LLM call), two
        reads at different simulated times must show different dates."""
        cm = ConversationManager()
        with patch("tarno.ai.prompts.builder.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 1, 8, 0, 0)
            first = cm.system_prompt
        with patch("tarno.ai.prompts.builder.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 12, 31, 23, 0, 0)
            second = cm.system_prompt
        self.assertIn("01.01.2026", first)
        self.assertIn("31.12.2026", second)
        self.assertNotEqual(first, second)

    def test_instructs_model_to_trust_tool_results_over_own_memory(self) -> None:
        cm = ConversationManager()
        self.assertIn("wortgetreu", cm.system_prompt)

    def test_instructs_model_never_to_invent_details_beyond_tool_results(self) -> None:
        """Regression test (found via live testing): describe_what_i_see's
        raw tool result was an accurate camera description, but the model's
        chat reply replaced it with fabricated, contradictory details across
        two separate calls - the same failure mode as the reminder-date
        hallucination, just for vision. This generalizes the existing
        tool-result-trust rule beyond just add_reminder's date/time."""
        cm = ConversationManager()
        self.assertIn("describe_what_i_see", cm.system_prompt)
        self.assertIn("GROUND TRUTH", cm.system_prompt)


if __name__ == "__main__":
    unittest.main()
