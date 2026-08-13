"""Tests for autonomous extensions (scheduler, reminders, routines, task planner)."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta

from tarno.core.action_result import ActionResult
from tarno.extensions.reminder import ReminderEngine
from tarno.extensions.routines import Routine, RoutineRunner, RoutineStep
from tarno.extensions.scheduler import TarnoScheduler, ScheduledTask
from tarno.extensions.task_planner import PlannedTask, TaskPlanner, TaskStatus


class SchedulerTests(unittest.TestCase):
    """Tests for the generic scheduler."""

    def test_daily_cron_match(self):
        scheduler = TarnoScheduler(tick_seconds=60)
        called = []
        task = ScheduledTask(
            id="t1",
            cron="12:30",
            action=lambda: called.append(True),
        )
        now = datetime(2026, 1, 1, 12, 30, 0)
        self.assertTrue(scheduler._should_run(task, now))

    def test_interval_cron_match(self):
        scheduler = TarnoScheduler(tick_seconds=60)
        called = []
        task = ScheduledTask(
            id="t1",
            cron="*/15",
            action=lambda: called.append(True),
        )
        now = datetime(2026, 1, 1, 10, 15, 0)
        self.assertTrue(scheduler._should_run(task, now))

    def test_no_rerun_within_same_minute(self):
        scheduler = TarnoScheduler(tick_seconds=60)
        task = ScheduledTask(id="t1", cron="12:30", action=lambda: None)
        now = datetime(2026, 1, 1, 12, 30, 0)
        self.assertTrue(scheduler._should_run(task, now))
        task.last_run = now
        self.assertFalse(scheduler._should_run(task, now))


class ReminderEngineTests(unittest.TestCase):
    """Tests for the reminder engine."""

    def test_add_and_list_due(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = ReminderEngine(storage_path=f"{tmp}/reminders.json")
            trigger = datetime.now() - timedelta(minutes=1)
            engine.add("Test", trigger, "Erinnerung!")
            due = engine.list_due()
            self.assertEqual(len(due), 1)

    def test_check_and_notify(self):
        with tempfile.TemporaryDirectory() as tmp:
            messages: list[str] = []
            engine = ReminderEngine(
                storage_path=f"{tmp}/reminders.json",
                notify_callback=messages.append,
            )
            trigger = datetime.now() - timedelta(minutes=1)
            engine.add("Test", trigger, "Erinnerung!")
            engine.check_and_notify()
            self.assertEqual(messages, ["Erinnerung!"])
            self.assertEqual(len(engine.list_due()), 0)


class RoutineRunnerTests(unittest.TestCase):
    """Tests for routine execution."""

    def test_match_and_run(self):
        calls: list[tuple[str, dict]] = []

        def executor(tool: str, params: dict):
            calls.append((tool, params))
            return "ok"

        with tempfile.TemporaryDirectory() as tmp:
            runner = RoutineRunner(executor, storage_path=f"{tmp}/routines.json")
            routine = Routine(
                id="r1",
                name="Guten Morgen",
                trigger_phrase="guten morgen",
                steps=[
                    RoutineStep(tool="open_application", params={"app_name": "Mail"}),
                ],
            )
            runner.register(routine)
            matched = runner.match("Guten Morgen TARNO")
            self.assertIsNotNone(matched)
            runner.run(matched)
        self.assertEqual(calls, [("open_application", {"app_name": "Mail"})])


class TaskPlannerTests(unittest.TestCase):
    """Tests for the human-in-the-loop task planner."""

    def test_create_and_approve(self):
        calls: list[tuple[str, dict]] = []

        def executor(tool: str, params: dict):
            calls.append((tool, params))
            return ActionResult(success=True, message="ok")

        with tempfile.TemporaryDirectory() as tmp:
            planner = TaskPlanner(
                approval_callback=lambda task: True,
                executor=executor,
                storage_path=f"{tmp}/tasks.json",
            )
            task = planner.create("Beispiel", [{"tool": "git_status", "params": {}}])
            result = planner.run(task.id)
            self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(calls, [("git_status", {})])

    def test_create_and_cancel(self):
        with tempfile.TemporaryDirectory() as tmp:
            planner = TaskPlanner(
                approval_callback=lambda task: False,
                executor=lambda t, p: None,
                storage_path=f"{tmp}/tasks.json",
            )
            task = planner.create("Beispiel", [{"tool": "x", "params": {}}])
            result = planner.run(task.id)
            self.assertEqual(result.status, TaskStatus.CANCELLED)

    def test_async_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls: list[tuple[str, dict]] = []

            def executor(tool: str, params: dict):
                calls.append((tool, params))
                return ActionResult(success=True, message="ok")

            planner = TaskPlanner(
                approval_callback=lambda task: None,
                executor=executor,
                storage_path=f"{tmp}/tasks.json",
            )
            task = planner.create("Beispiel", [{"tool": "x", "params": {}}])
            result = planner.run(task.id)
            self.assertEqual(result.status, TaskStatus.PENDING)
            self.assertEqual(calls, [])
            approved = planner.approve(task.id)
            self.assertEqual(approved.status, TaskStatus.COMPLETED)
            self.assertEqual(calls, [("x", {})])


if __name__ == "__main__":
    unittest.main()
