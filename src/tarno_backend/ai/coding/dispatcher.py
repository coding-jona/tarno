"""Selects the concrete coding backend for the configured provider/backend."""

from __future__ import annotations

from typing import Any

from tarno_backend.ai.coding.adapters.aider_adapter import AiderBackend
from tarno_backend.ai.coding.adapters.base import CodingBackend as CodingBackendABC
from tarno_backend.ai.coding.adapters.native_agent import NativeAgentBackend
from tarno_backend.ai.coding.exceptions import UnsupportedProviderError


class CodingDispatcher:
    """Returns the right ``CodingBackend`` for a provider slug."""

    def __init__(self, config, secrets: Any | None = None) -> None:
        self.config = config
        self.secrets = secrets

    def get_backend(self, provider: str | None = None) -> CodingBackendABC:
        provider = provider or self.config.coding.provider
        if provider not in ("mistral", "ollama", "claude", "openai"):
            raise UnsupportedProviderError(
                f"Coding-Provider '{provider}' wird noch nicht unterstützt."
            )

        # CodingConfig.backend (default "native"): eigene Tool-Calling-
        # Schleife statt Aiders SEARCH/REPLACE-Diff-Format - siehe
        # native_agent.py Docstring für die Begründung. "aider" bleibt als
        # expliziter Opt-out erhalten (z.B. falls jemand Aiders eingebaute
        # Repo-Map/Multi-File-Coordination gezielt haben will), ist aber
        # nicht mehr der Default.
        backend = getattr(self.config.coding, "backend", "native")
        if backend == "aider":
            return AiderBackend(self.config, self.secrets)
        return NativeAgentBackend(self.config, self.secrets)
