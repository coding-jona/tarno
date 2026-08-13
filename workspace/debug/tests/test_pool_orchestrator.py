"""Tests for tarno/ai/pool/orchestrator.py (Agent-Pool Phase 2)."""

from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass, field
from unittest.mock import MagicMock

from tarno_backend.ai.pool.models import PoolAgentSpec, PoolConfig, PoolMessage
from tarno_backend.ai.pool.orchestrator import PoolOrchestrator, _parse_subtasks
from tarno_backend.ai.pool.worker import PoolWorker


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


@dataclass
class _FakeCodingConfig:
    pool_max_lead_iterations: int = 3
    pool_worker_max_tool_iterations: int = 4


@dataclass
class _FakeConfig:
    coding: _FakeCodingConfig = field(default_factory=_FakeCodingConfig)


def _spec(provider: str, model: str, role: str) -> PoolAgentSpec:
    return PoolAgentSpec(provider=provider, model=model, role=role)


class ParseSubtasksTests(unittest.TestCase):
    def test_parses_two_blocks(self) -> None:
        text = (
            "### AUFGABE für claude:x\n"
            "Docstring zu Funktion X hinzufügen\n"
            "### AUFGABE für mistral:y\n"
            "Kommentar zu Funktion Y hinzufügen\n"
        )
        subtasks = _parse_subtasks(text, {"claude:x", "mistral:y"})
        self.assertEqual(len(subtasks), 2)
        self.assertEqual(subtasks[0].assigned_to, "claude:x")
        self.assertIn("Funktion X", subtasks[0].description)
        self.assertEqual(subtasks[1].assigned_to, "mistral:y")
        self.assertIn("Funktion Y", subtasks[1].description)

    def test_ignores_unknown_slug(self) -> None:
        text = "### AUFGABE für unbekannt:z\nEtwas tun\n"
        subtasks = _parse_subtasks(text, {"claude:x"})
        self.assertEqual(subtasks, [])

    def test_empty_text_yields_no_subtasks(self) -> None:
        self.assertEqual(_parse_subtasks("", {"claude:x"}), [])


def _make_orchestrator(lead_responses: list[str], worker_responses: dict[str, str]) -> PoolOrchestrator:
    lead_spec = _spec("mistral", "mistral-large-latest", "lead")
    worker_specs = [
        _spec(p, m, "worker") for p, m in [("claude", "claude-x"), ("groq", "groq-y")]
    ]
    pool_config = PoolConfig((lead_spec, *worker_specs))

    lead_provider = MagicMock()
    lead_provider.send.side_effect = [_FakeResponse(t) for t in lead_responses]
    lead_worker = PoolWorker(lead_spec, config=None, provider=lead_provider)

    workers = {lead_spec.slug: lead_worker}
    for spec in worker_specs:
        provider = MagicMock()
        provider.send.return_value = _FakeResponse(worker_responses.get(spec.slug, "ok"))
        workers[spec.slug] = PoolWorker(spec, config=None, provider=provider)

    orchestrator = PoolOrchestrator(_FakeConfig(), pool_config, workers=workers)
    return orchestrator


class RunTests(unittest.TestCase):
    def test_full_run_decompose_dispatch_merge(self) -> None:
        lead_spec = _spec("mistral", "mistral-large-latest", "lead")
        claude_slug = "claude:claude-x"
        groq_slug = "groq:groq-y"
        decompose_response = (
            f"### AUFGABE für {claude_slug}\nDocstring hinzufügen\n"
            f"### AUFGABE für {groq_slug}\nKommentar hinzufügen\n"
        )
        orchestrator = _make_orchestrator(
            lead_responses=[decompose_response, "Finale Anweisung: alles anwenden."],
            worker_responses={claude_slug: "Docstring-Vorschlag", groq_slug: "Kommentar-Vorschlag"},
        )

        messages: list[PoolMessage] = []
        result = asyncio.run(orchestrator.run("Docstrings und Kommentare ergänzen", on_message=messages.append))

        self.assertEqual(result.kind, "merge_decision")
        self.assertEqual(result.text, "Finale Anweisung: alles anwenden.")
        kinds = [m.kind for m in messages]
        self.assertIn("assign", kinds)
        self.assertIn("report", kinds)
        self.assertIn("merge_decision", kinds)
        report_texts = [m.text for m in messages if m.kind == "report"]
        self.assertIn("Docstring-Vorschlag", report_texts)
        self.assertIn("Kommentar-Vorschlag", report_texts)

    def test_no_parseable_subtasks_returns_early_status(self) -> None:
        orchestrator = _make_orchestrator(
            lead_responses=["Ich verstehe die Aufgabe nicht, keine gültigen Blöcke."],
            worker_responses={},
        )

        result = asyncio.run(orchestrator.run("Unklare Aufgabe"))

        self.assertEqual(result.kind, "merge_decision")
        self.assertIn("nicht", result.text.lower())

    def test_revision_marker_triggers_second_round(self) -> None:
        lead_spec = _spec("mistral", "mistral-large-latest", "lead")
        claude_slug = "claude:claude-x"
        groq_slug = "groq:groq-y"
        decompose_response = (
            f"### AUFGABE für {claude_slug}\nA\n"
            f"### AUFGABE für {groq_slug}\nB\n"
        )
        orchestrator = _make_orchestrator(
            lead_responses=[
                decompose_response,
                "REVISION NÖTIG: brauche mehr Details von claude",
                "Finale Anweisung nach Revision.",
            ],
            worker_responses={claude_slug: "Vorschlag A", groq_slug: "Vorschlag B"},
        )

        result = asyncio.run(orchestrator.run("Aufgabe mit Revision"))

        self.assertEqual(result.text, "Finale Anweisung nach Revision.")

    def test_iteration_limit_returns_best_effort_after_repeated_revisions(self) -> None:
        lead_spec = _spec("mistral", "mistral-large-latest", "lead")
        claude_slug = "claude:claude-x"
        groq_slug = "groq:groq-y"
        decompose_response = (
            f"### AUFGABE für {claude_slug}\nA\n"
            f"### AUFGABE für {groq_slug}\nB\n"
        )
        orchestrator = _make_orchestrator(
            lead_responses=[
                decompose_response,
                "REVISION NÖTIG: 1",
                "REVISION NÖTIG: 2",
                "REVISION NÖTIG: 3",
            ],
            worker_responses={claude_slug: "Vorschlag A", groq_slug: "Vorschlag B"},
        )
        orchestrator._config.coding.pool_max_lead_iterations = 3

        result = asyncio.run(orchestrator.run("Endlose Revision"))

        self.assertTrue(result.text.startswith("REVISION NÖTIG"))


if __name__ == "__main__":
    unittest.main()
