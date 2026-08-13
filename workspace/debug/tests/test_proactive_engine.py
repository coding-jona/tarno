"""Tests for the autonomous trigger engine (Block 3, Phasen 21-30).

Covers each observer's scoring logic in isolation plus the engine's
cooldown/debounce behavior (Phase 30 - the stress test against endless
speech loops from a sustained condition like high RAM or an ongoing
distraction).
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from tarno_backend.core.calendar_service import CalendarEvent
from tarno_backend.core.proactive_engine import (
    IdleCuriosityObserver,
    ProactiveDraft,
    ProactiveEngine,
    SystemObserver,
    TimeCalendarObserver,
    UserBehaviorObserver,
    clamp_score,
)


class ClampScoreTests(unittest.TestCase):
    def test_clamps_to_0_100(self) -> None:
        self.assertEqual(clamp_score(-10), 0)
        self.assertEqual(clamp_score(150), 100)
        self.assertEqual(clamp_score(42.4), 42)
        self.assertEqual(clamp_score(42.6), 43)


class _FakeCalendar:
    def __init__(self, events: list[CalendarEvent]) -> None:
        self._events = events

    def get_upcoming_events(self, days_ahead: int = 1) -> list[CalendarEvent]:
        return self._events


class TimeCalendarObserverTests(unittest.TestCase):
    def test_drafts_when_event_within_lookahead(self) -> None:
        soon = datetime.now() + timedelta(minutes=5)
        calendar = _FakeCalendar([CalendarEvent(summary="Standup", start=soon)])
        observer = TimeCalendarObserver(calendar, lookahead_minutes=15)

        draft = observer.check()
        self.assertIsNotNone(draft)
        self.assertEqual(draft.source, "calendar")
        self.assertGreaterEqual(draft.score, 70)
        self.assertIn("Standup", draft.message)

    def test_does_not_redraft_same_event(self) -> None:
        soon = datetime.now() + timedelta(minutes=5)
        calendar = _FakeCalendar([CalendarEvent(summary="Standup", start=soon)])
        observer = TimeCalendarObserver(calendar, lookahead_minutes=15)

        first = observer.check()
        second = observer.check()
        self.assertIsNotNone(first)
        self.assertIsNone(second)

    def test_ignores_events_outside_lookahead(self) -> None:
        far = datetime.now() + timedelta(minutes=60)
        calendar = _FakeCalendar([CalendarEvent(summary="Later", start=far)])
        observer = TimeCalendarObserver(calendar, lookahead_minutes=15)
        self.assertIsNone(observer.check())

    def test_ignores_all_day_events(self) -> None:
        from datetime import date
        calendar = _FakeCalendar([CalendarEvent(summary="All day", start=date.today())])
        observer = TimeCalendarObserver(calendar, lookahead_minutes=15)
        self.assertIsNone(observer.check())


class SystemObserverTests(unittest.TestCase):
    def test_no_draft_below_thresholds(self) -> None:
        observer = SystemObserver(cpu_threshold=90, ram_threshold=90, disk_threshold=90)
        with patch("psutil.cpu_percent", return_value=10.0), \
             patch("psutil.virtual_memory") as mem, \
             patch("psutil.disk_usage") as disk:
            mem.return_value.percent = 20.0
            disk.return_value.percent = 30.0
            self.assertIsNone(observer.check())

    def test_drafts_when_ram_exceeds_threshold(self) -> None:
        observer = SystemObserver(cpu_threshold=90, ram_threshold=90, disk_threshold=90)
        with patch("psutil.cpu_percent", return_value=10.0), \
             patch("psutil.virtual_memory") as mem, \
             patch("psutil.disk_usage") as disk:
            mem.return_value.percent = 97.0
            disk.return_value.percent = 30.0
            draft = observer.check()
        self.assertIsNotNone(draft)
        self.assertEqual(draft.source, "system")
        self.assertIn("Arbeitsspeicher", draft.message)

    def test_reports_only_worst_offender(self) -> None:
        observer = SystemObserver(cpu_threshold=90, ram_threshold=90, disk_threshold=90)
        with patch("psutil.cpu_percent", return_value=92.0), \
             patch("psutil.virtual_memory") as mem, \
             patch("psutil.disk_usage") as disk:
            mem.return_value.percent = 99.0  # bigger overage than CPU
            disk.return_value.percent = 30.0
            draft = observer.check()
        self.assertIn("Arbeitsspeicher", draft.message)


class UserBehaviorObserverTests(unittest.TestCase):
    def _make_observer(self, **overrides) -> UserBehaviorObserver:
        defaults = dict(
            distraction_apps=["youtube"],
            calendar_service=_FakeCalendar([]),
            minutes_before_action=0.0,  # trigger immediately in tests
            calendar_lookahead_minutes=15,
            close_distraction_window=False,
        )
        defaults.update(overrides)
        return UserBehaviorObserver(**defaults)

    def test_no_draft_when_not_distracted(self) -> None:
        observer = self._make_observer()
        with patch(
            "tarno_backend.desktop.window_manager.get_active_window",
            return_value={"title": "Visual Studio Code"},
        ):
            self.assertIsNone(observer.check())

    def test_baseline_nudge_without_imminent_event(self) -> None:
        observer = self._make_observer()
        with patch(
            "tarno_backend.desktop.window_manager.get_active_window",
            return_value={"title": "YouTube - Chrome"},
        ):
            first = observer.check()  # establishes distraction_since
            second = observer.check()  # minutes_before_action=0, so this drafts
        self.assertIsNone(first)
        self.assertIsNotNone(second)
        self.assertIsNone(second.action)
        self.assertLess(second.score, 90)

    def test_escalates_with_imminent_event_and_closes_window(self) -> None:
        soon = datetime.now() + timedelta(minutes=5)
        calendar = _FakeCalendar([CalendarEvent(summary="Meeting", start=soon)])
        observer = self._make_observer(calendar_service=calendar, close_distraction_window=True)
        with patch(
            "tarno_backend.desktop.window_manager.get_active_window",
            return_value={"title": "YouTube - Chrome"},
        ):
            observer.check()  # establishes distraction_since
            draft = observer.check()
        self.assertIsNotNone(draft)
        self.assertEqual(draft.action, "close_window")
        self.assertEqual(draft.action_params["title_substring"], "YouTube - Chrome")
        self.assertGreaterEqual(draft.score, 90)


class _FakeTask:
    def __init__(self, description: str, created_at: datetime) -> None:
        self.description = description
        self.created_at = created_at


class _FakeTaskPlanner:
    def __init__(self, pending: list) -> None:
        self._pending = pending

    def list_pending(self) -> list:
        return self._pending


class IdleCuriosityObserverTests(unittest.TestCase):
    def test_no_draft_when_not_idle_long_enough(self) -> None:
        planner = _FakeTaskPlanner([_FakeTask("Etwas erledigen", datetime.now())])
        observer = IdleCuriosityObserver(
            task_planner=planner,
            get_last_interaction=lambda: datetime.now(),
            idle_minutes=15,
        )
        self.assertIsNone(observer.check())

    def test_drafts_when_idle_and_pending_tasks_exist(self) -> None:
        planner = _FakeTaskPlanner([_FakeTask("Etwas erledigen", datetime.now())])
        observer = IdleCuriosityObserver(
            task_planner=planner,
            get_last_interaction=lambda: datetime.now() - timedelta(minutes=20),
            idle_minutes=15,
        )
        draft = observer.check()
        self.assertIsNotNone(draft)
        self.assertIn("Etwas erledigen", draft.message)

    def test_no_draft_when_idle_but_no_pending_tasks(self) -> None:
        planner = _FakeTaskPlanner([])
        observer = IdleCuriosityObserver(
            task_planner=planner,
            get_last_interaction=lambda: datetime.now() - timedelta(minutes=20),
            idle_minutes=15,
        )
        self.assertIsNone(observer.check())


class _AlwaysHighScoreObserver:
    name = "always_high"

    def __init__(self) -> None:
        self.calls = 0

    def check(self) -> ProactiveDraft:
        self.calls += 1
        return ProactiveDraft(source=self.name, message="Test", score=95)


class _FailingObserver:
    name = "broken"

    def check(self) -> ProactiveDraft | None:
        raise RuntimeError("boom")


class ProactiveEngineCooldownTests(unittest.TestCase):
    """Phase 30: proves a sustained high-score condition can't retrigger
    on_trigger() faster than source_cooldown_seconds - the mechanism that
    prevents an endless autonomous-speech loop."""

    def test_debounces_repeated_high_score_draft(self) -> None:
        observer = _AlwaysHighScoreObserver()
        triggered: list[ProactiveDraft] = []
        engine = ProactiveEngine(
            observers=[observer],
            on_trigger=triggered.append,
            score_threshold=85,
            source_cooldown_seconds=300.0,
        )

        # Simulate three consecutive ticks in quick succession.
        engine._check_one(observer)
        engine._check_one(observer)
        engine._check_one(observer)

        self.assertEqual(observer.calls, 3)
        self.assertEqual(len(triggered), 1)  # only the first tick actually triggered

    def test_below_threshold_never_triggers(self) -> None:
        class _LowScoreObserver:
            name = "low"

            def check(self) -> ProactiveDraft:
                return ProactiveDraft(source=self.name, message="meh", score=50)

        triggered: list[ProactiveDraft] = []
        engine = ProactiveEngine(
            observers=[_LowScoreObserver()],
            on_trigger=triggered.append,
            score_threshold=85,
        )
        engine._check_one(_LowScoreObserver())
        self.assertEqual(triggered, [])

    def test_broken_observer_does_not_crash_engine(self) -> None:
        triggered: list[ProactiveDraft] = []
        engine = ProactiveEngine(observers=[_FailingObserver()], on_trigger=triggered.append)
        # Should log and swallow the exception, not propagate.
        engine._check_one(_FailingObserver())
        self.assertEqual(triggered, [])


class DynamicObserverManagementTests(unittest.TestCase):
    """Regression coverage for the camera-can't-be-enabled bug: an engine
    constructed with zero observers (e.g. proactive.enabled=false at
    startup) must still let a new observer be attached and ticked later -
    this is exactly what Block 7's live vision opt-in relies on."""

    def test_add_observer_to_empty_engine_gets_ticked(self) -> None:
        engine = ProactiveEngine(observers=[], on_trigger=lambda draft: None)
        observer = _AlwaysHighScoreObserver()
        engine.add_observer(observer)
        engine._check_one(observer)
        self.assertEqual(observer.calls, 1)

    def test_adding_same_observer_twice_is_a_noop(self) -> None:
        engine = ProactiveEngine(observers=[], on_trigger=lambda draft: None)
        observer = _AlwaysHighScoreObserver()
        engine.add_observer(observer)
        engine.add_observer(observer)
        with engine._observers_lock:
            self.assertEqual(engine._observers.count(observer), 1)

    def test_remove_observer(self) -> None:
        observer = _AlwaysHighScoreObserver()
        engine = ProactiveEngine(observers=[observer], on_trigger=lambda draft: None)
        engine.remove_observer(observer)
        with engine._observers_lock:
            self.assertNotIn(observer, engine._observers)

    def test_remove_observer_not_present_is_safe(self) -> None:
        engine = ProactiveEngine(observers=[], on_trigger=lambda draft: None)
        engine.remove_observer(_AlwaysHighScoreObserver())  # should not raise


if __name__ == "__main__":
    unittest.main()
