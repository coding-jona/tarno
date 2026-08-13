"""Tests for tarno/ai/context/usage_tracker.py (Kontext-Effizienz Phase 3)."""

from __future__ import annotations

import unittest

from tarno.ai.context.usage_tracker import ContextUsageTracker


class RecordTests(unittest.TestCase):
    def test_real_provider_usage_sets_ratio(self) -> None:
        tracker = ContextUsageTracker()
        tracker.record(tokens_used=7500, context_window=10000)
        self.assertAlmostEqual(tracker.last_known_ratio, 0.75)
        self.assertFalse(tracker.last_ratio_is_estimate)

    def test_none_usage_leaves_ratio_untouched_sticky(self) -> None:
        tracker = ContextUsageTracker()
        tracker.record(tokens_used=5000, context_window=10000)
        tracker.record(tokens_used=None, context_window=None)
        self.assertAlmostEqual(tracker.last_known_ratio, 0.5)


class EstimateFallbackTests(unittest.TestCase):
    def test_estimate_used_when_no_real_data_ever_reported(self) -> None:
        tracker = ContextUsageTracker(default_context_window=1000)
        messages = [{"role": "user", "content": "x" * 4000}]
        tracker.record_estimate(messages)
        self.assertIsNotNone(tracker.last_known_ratio)
        self.assertTrue(tracker.last_ratio_is_estimate)
        self.assertAlmostEqual(tracker.last_known_ratio, 1.0)

    def test_real_data_overwrites_prior_estimate(self) -> None:
        tracker = ContextUsageTracker(default_context_window=1000)
        tracker.record_estimate([{"role": "user", "content": "x" * 4000}])
        self.assertTrue(tracker.last_ratio_is_estimate)
        tracker.record(tokens_used=100, context_window=1000)
        self.assertFalse(tracker.last_ratio_is_estimate)
        self.assertAlmostEqual(tracker.last_known_ratio, 0.1)


class ShouldSummarizeTests(unittest.TestCase):
    def test_below_threshold_never_triggers(self) -> None:
        tracker = ContextUsageTracker()
        tracker.record(tokens_used=1000, context_window=10000)
        self.assertFalse(tracker.should_summarize())

    def test_at_threshold_with_cooldown_satisfied_triggers(self) -> None:
        tracker = ContextUsageTracker(cooldown_messages=2)
        tracker.record(tokens_used=8000, context_window=10000)
        tracker.record(tokens_used=8000, context_window=10000)
        self.assertTrue(tracker.should_summarize())

    def test_cooldown_blocks_immediate_retrigger(self) -> None:
        tracker = ContextUsageTracker(cooldown_messages=4)
        tracker.record(tokens_used=8000, context_window=10000)
        self.assertFalse(tracker.should_summarize())

    def test_reset_after_summary_restarts_cooldown(self) -> None:
        tracker = ContextUsageTracker(cooldown_messages=2)
        tracker.record(tokens_used=8000, context_window=10000)
        tracker.record(tokens_used=8000, context_window=10000)
        self.assertTrue(tracker.should_summarize())
        tracker.reset_after_summary()
        self.assertFalse(tracker.should_summarize())
        tracker.record(tokens_used=8000, context_window=10000)
        tracker.record(tokens_used=8000, context_window=10000)
        self.assertTrue(tracker.should_summarize())

    def test_no_data_at_all_never_triggers(self) -> None:
        tracker = ContextUsageTracker()
        self.assertFalse(tracker.should_summarize())


if __name__ == "__main__":
    unittest.main()
