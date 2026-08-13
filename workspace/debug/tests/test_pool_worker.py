"""Tests for tarno/ai/pool/worker.py (Agent-Pool Phase 1)."""

from __future__ import annotations

import asyncio
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

from tarno_backend.ai.pool.models import PoolAgentSpec, PoolMessage, SubTask
from tarno_backend.ai.pool.worker import PoolWorker


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


def _make_worker(role: str, response_text: str = "Vorschlag des Workers", delay: float = 0.0) -> PoolWorker:
    spec = PoolAgentSpec(provider="mistral", model="mistral-small-latest", role=role)
    provider = MagicMock()

    def _send(*args, **kwargs):
        if delay:
            time.sleep(delay)
        return _FakeResponse(response_text)

    provider.send.side_effect = _send
    return PoolWorker(spec, config=None, provider=provider)


class RunSubtaskTests(unittest.TestCase):
    def test_returns_report_message_addressed_to_lead(self) -> None:
        worker = _make_worker("worker")
        subtask = SubTask(id="st-1", description="Füge einen Docstring hinzu", assigned_to=worker.agent_spec.slug)

        message = asyncio.run(worker.run_subtask(subtask, context=[]))

        self.assertEqual(message.kind, "report")
        self.assertEqual(message.to_agent, "lead")
        self.assertEqual(message.from_agent, worker.agent_spec.slug)
        self.assertEqual(message.sub_task_id, "st-1")
        self.assertEqual(message.text, "Vorschlag des Workers")

    def test_prompt_includes_subtask_description(self) -> None:
        spec = PoolAgentSpec(provider="mistral", model="m", role="worker")
        provider = MagicMock()
        provider.send.return_value = _FakeResponse("ok")
        worker = PoolWorker(spec, config=None, provider=provider)
        subtask = SubTask(id="st-1", description="Ganz bestimmte Teilaufgabe X", assigned_to=spec.slug)

        asyncio.run(worker.run_subtask(subtask, context=[]))

        sent_prompt = provider.send.call_args.kwargs["messages"][0]["content"]
        self.assertIn("Ganz bestimmte Teilaufgabe X", sent_prompt)

    def test_prompt_includes_prior_pool_context(self) -> None:
        spec = PoolAgentSpec(provider="mistral", model="m", role="worker")
        provider = MagicMock()
        provider.send.return_value = _FakeResponse("ok")
        worker = PoolWorker(spec, config=None, provider=provider)
        subtask = SubTask(id="st-1", description="X", assigned_to=spec.slug)
        context = [PoolMessage(from_agent="lead", to_agent="broadcast", kind="assign", text="Kontext-Hinweis ABC")]

        asyncio.run(worker.run_subtask(subtask, context=context))

        sent_prompt = provider.send.call_args.kwargs["messages"][0]["content"]
        self.assertIn("Kontext-Hinweis ABC", sent_prompt)

    def test_provider_failure_is_reported_not_raised(self) -> None:
        spec = PoolAgentSpec(provider="mistral", model="m", role="worker")
        provider = MagicMock()
        provider.send.side_effect = RuntimeError("API down")
        worker = PoolWorker(spec, config=None, provider=provider)
        subtask = SubTask(id="st-1", description="X", assigned_to=spec.slug)

        message = asyncio.run(worker.run_subtask(subtask, context=[]))

        self.assertEqual(message.kind, "report")
        self.assertIn("Fehler", message.text)

    def test_worker_role_uses_worker_system_prompt(self) -> None:
        spec = PoolAgentSpec(provider="mistral", model="m", role="worker")
        provider = MagicMock()
        provider.send.return_value = _FakeResponse("ok")
        worker = PoolWorker(spec, config=None, provider=provider)
        subtask = SubTask(id="st-1", description="X", assigned_to=spec.slug)

        asyncio.run(worker.run_subtask(subtask, context=[]))

        from tarno_backend.ai.prompts.pool_system import WORKER_SYSTEM_PROMPT
        self.assertEqual(provider.send.call_args.kwargs["system"], WORKER_SYSTEM_PROMPT)


class ConcurrencyTests(unittest.TestCase):
    def test_multiple_workers_run_concurrently_not_sequentially(self) -> None:
        """Matches the plan's Checkpoint 1: wall-clock ~= max(t1,t2), not t1+t2."""
        delay = 0.3
        worker_a = _make_worker("worker", delay=delay)
        worker_b = _make_worker("worker", delay=delay)
        subtask_a = SubTask(id="a", description="A", assigned_to=worker_a.agent_spec.slug)
        subtask_b = SubTask(id="b", description="B", assigned_to=worker_b.agent_spec.slug)

        async def _run_both() -> None:
            with ThreadPoolExecutor(max_workers=4) as executor:
                await asyncio.gather(
                    worker_a.run_subtask(subtask_a, context=[], executor=executor),
                    worker_b.run_subtask(subtask_b, context=[], executor=executor),
                )

        started = time.monotonic()
        asyncio.run(_run_both())
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, delay * 1.8)


if __name__ == "__main__":
    unittest.main()
