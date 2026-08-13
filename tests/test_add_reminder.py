"""Tests for TarnoEngine._resolve_reminder_time (the add_reminder tool's
date/time computation, extracted as a pure static method for testability).

Built after a live test revealed that when the LLM was asked to compute a
full absolute datetime itself for a chat-mentioned appointment, it got the
date wrong (wrote 2024-07-23 instead of the actual current date). This tool
avoids that failure mode entirely by only ever asking the model for a time
(and optionally a date) - "today"/"tomorrow" rollover is computed here in
code, never guessed by the model.
"""

from __future__ import annotations

import unittest
from datetime import datetime

from tarno.core.engine import TarnoEngine


class ResolveReminderTimeTests(unittest.TestCase):
    def test_time_only_later_today_stays_today(self) -> None:
        now = datetime(2026, 7, 19, 18, 0, 0)
        trigger, error = TarnoEngine._resolve_reminder_time("19:20", None, now=now)
        self.assertIsNone(error)
        self.assertEqual(trigger, datetime(2026, 7, 19, 19, 20, 0))

    def test_time_only_already_passed_today_rolls_to_tomorrow(self) -> None:
        now = datetime(2026, 7, 19, 20, 0, 0)
        trigger, error = TarnoEngine._resolve_reminder_time("19:20", None, now=now)
        self.assertIsNone(error)
        self.assertEqual(trigger, datetime(2026, 7, 20, 19, 20, 0))

    def test_explicit_date_is_used_verbatim(self) -> None:
        now = datetime(2026, 7, 19, 12, 0, 0)
        trigger, error = TarnoEngine._resolve_reminder_time("09:00", "2026-08-01", now=now)
        self.assertIsNone(error)
        self.assertEqual(trigger, datetime(2026, 8, 1, 9, 0, 0))

    def test_explicit_past_date_is_rejected(self) -> None:
        """Found via live testing: even with the system-prompt date-injection
        fix (see test_system_prompt_date.py), the model still occasionally
        hallucinates a past year (e.g. '2024-07-24' when 'now' was actually
        2026-07-19) when asked to fill in an explicit date - honoring it
        verbatim silently stored a reminder that could never fire. An
        explicit date resulting in a past trigger_time is now rejected with
        an error carrying the real current date, so the model gets corrected
        via the tool result instead of the reminder silently going dead."""
        now = datetime(2026, 7, 19, 12, 0, 0)
        trigger, error = TarnoEngine._resolve_reminder_time("09:00", "2020-01-01", now=now)
        self.assertIsNone(trigger)
        self.assertEqual(error.error_code, "PastDate")
        self.assertIn("2026-07-19", error.message)

    def test_explicit_date_today_with_already_passed_time_is_rejected(self) -> None:
        now = datetime(2026, 7, 19, 20, 0, 0)
        trigger, error = TarnoEngine._resolve_reminder_time("09:00", "2026-07-19", now=now)
        self.assertIsNone(trigger)
        self.assertEqual(error.error_code, "PastDate")

    def test_invalid_time_format_returns_error(self) -> None:
        trigger, error = TarnoEngine._resolve_reminder_time("25:99", None, now=datetime.now())
        self.assertIsNone(trigger)
        self.assertIsNotNone(error)
        self.assertEqual(error.error_code, "InvalidTime")

    def test_non_numeric_time_returns_error(self) -> None:
        trigger, error = TarnoEngine._resolve_reminder_time("abendessen", None, now=datetime.now())
        self.assertIsNone(trigger)
        self.assertEqual(error.error_code, "InvalidTime")

    def test_invalid_date_format_returns_error(self) -> None:
        trigger, error = TarnoEngine._resolve_reminder_time("19:20", "23.07.2024", now=datetime.now())
        self.assertIsNone(trigger)
        self.assertEqual(error.error_code, "InvalidDate")

    def test_exact_current_minute_rolls_to_tomorrow(self) -> None:
        """trigger_time <= now (not just <) rolls over - a reminder set for
        "right now" should fire tomorrow, not be silently already-due."""
        now = datetime(2026, 7, 19, 19, 20, 0)
        trigger, error = TarnoEngine._resolve_reminder_time("19:20", None, now=now)
        self.assertIsNone(error)
        self.assertEqual(trigger, datetime(2026, 7, 20, 19, 20, 0))


if __name__ == "__main__":
    unittest.main()
