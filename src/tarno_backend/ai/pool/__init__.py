"""TARNO Agent-Pool: mehrere LLM-Provider kollaborieren an einer Coding-Aufgabe.

Separat vom Einzel-Agent-Pfad (tarno/ai/coding/, AiderBackend) - siehe
Phase-0-Kommentar in models.py fuer den architektonischen Grund.
"""

from __future__ import annotations

from tarno_backend.ai.pool.models import PoolAgentSpec, PoolConfig, PoolMessage, SubTask
from tarno_backend.ai.pool.orchestrator import PoolOrchestrator
from tarno_backend.ai.pool.worker import PoolWorker

__all__ = [
    "PoolAgentSpec",
    "PoolConfig",
    "PoolMessage",
    "SubTask",
    "PoolWorker",
    "PoolOrchestrator",
]
