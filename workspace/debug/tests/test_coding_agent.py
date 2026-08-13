"""Tests for the high-level CodingAgent."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from typing import Any, Iterator

from tarno_backend.ai.coding.agent import CodingAgent
from tarno_backend.ai.coding.protocol import CodingOutput
from tarno_backend.core.action_result import ActionResult
from tarno_backend.core.config import TarnoConfig
from tarno_backend.core.events import EventBus


class _FakeBackend:
    """Fake coding backend for unit tests."""

    def __init__(self, outputs: list[CodingOutput] | None = None) -> None:
        self.outputs = outputs or [CodingOutput(kind="summary", text="done")]

    def run(
        self,
        prompt: str,
        workspace: dict[str, Any],
        fnames: list[str],
        read_only: bool,
        on_output=None,
    ) -> Iterator[CodingOutput]:
        for output in self.outputs:
            if on_output:
                on_output(output)
            yield output


def _make_agent(workspace: dict[str, Any] | None = None, mode: str = "ultimate") -> CodingAgent:
    config = TarnoConfig()
    config.command_execution.autonomy_mode = mode
    return CodingAgent(
        config,
        event_bus=EventBus(),
        get_workspace=lambda: workspace,
    )


class CodingAgentTests(unittest.TestCase):
    def test_no_workspace(self) -> None:
        agent = _make_agent(workspace=None)
        agent.dispatcher.get_backend = lambda: _FakeBackend()
        result = agent.execute_task("test prompt")
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "NoWorkspace")

    def test_execute_task_success(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".git"))
            workspace = {"folders": [{"path": root}]}
            agent = _make_agent(workspace=workspace, mode="ultimate")
            agent.dispatcher.get_backend = lambda: _FakeBackend()
            result = agent.execute_task("test prompt")
            self.assertTrue(result.success)
            self.assertEqual(result.message, "done")

    def test_read_only_for_balanced(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".git"))
            workspace = {"folders": [{"path": root}]}
            agent = _make_agent(workspace=workspace, mode="balanced")
            received: list[bool] = []

            class _RoBackend(_FakeBackend):
                def run(self, prompt, workspace, fnames, read_only, on_output=None):
                    received.append(read_only)
                    return super().run(prompt, workspace, fnames, read_only, on_output)

            agent.dispatcher.get_backend = lambda: _RoBackend()
            agent.execute_task("test prompt")
            self.assertEqual(received, [True])

    def test_read_only_override(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".git"))
            workspace = {"folders": [{"path": root}]}
            agent = _make_agent(workspace=workspace, mode="ultimate")
            received: list[bool] = []

            class _RoBackend(_FakeBackend):
                def run(self, prompt, workspace, fnames, read_only, on_output=None):
                    received.append(read_only)
                    return super().run(prompt, workspace, fnames, read_only, on_output)

            agent.dispatcher.get_backend = lambda: _RoBackend()
            agent.execute_task("test prompt", read_only=True)
            self.assertEqual(received, [True])

    def test_path_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".git"))
            outside = tempfile.mkdtemp()
            try:
                workspace = {"folders": [{"path": root}]}
                agent = _make_agent(workspace=workspace, mode="ultimate")
                agent.dispatcher.get_backend = lambda: _FakeBackend()
                result = agent.execute_task(
                    "test prompt",
                    file_paths=[os.path.join(outside, "evil.py")],
                )
                self.assertFalse(result.success)
                self.assertEqual(result.error_code, "PathOutsideWorkspace")
            finally:
                shutil.rmtree(outside)
