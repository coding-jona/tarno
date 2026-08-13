"""Wendet die finale, vom Lead zusammengeführte Anweisung über die
bestehende, UNVERÄNDERTE AiderBackend an (Coding-Agent-Pool-Plan Phase 2).

AiderBackend selbst bekommt keinen neuen Pool-Code - sie wird exakt wie im
Einzel-Agent-Pfad aufgerufen, nur mit einem pool-synthetisierten Prompt
statt einem nutzergetippten. Die ausführende Provider/Modell-Identität ist
die des Lead-Agenten: AiderBackend liest provider/model aus
config.coding.provider/.model (nicht als run()-Parameter), daher wird hier
eine Config-KOPIE (dataclasses.replace) mit den Lead-Werten gebaut, statt
AiderBackend selbst zu ändern.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, Iterator

from tarno_backend.ai.coding.adapters.aider_adapter import AiderBackend
from tarno_backend.ai.coding.adapters.base import OnOutput
from tarno_backend.ai.coding.protocol import CodingOutput
from tarno_backend.ai.pool.models import PoolAgentSpec

if TYPE_CHECKING:
    from tarno_backend.core.config import TarnoConfig


def apply_merged_instruction(
    lead: PoolAgentSpec,
    config: "TarnoConfig",
    final_instruction: str,
    workspace: dict[str, Any],
    fnames: list[str],
    read_only: bool,
    secrets: Any = None,
    on_output: OnOutput | None = None,
) -> Iterator[CodingOutput]:
    """Führt final_instruction über AiderBackend aus, mit dem Lead-Agenten
    als ausführender Provider/Modell-Identität."""
    lead_config = dataclasses.replace(
        config,
        coding=dataclasses.replace(config.coding, provider=lead.provider, model=lead.model),
    )
    backend = AiderBackend(lead_config, secrets=secrets)
    yield from backend.run(final_instruction, workspace, fnames, read_only, on_output=on_output)
