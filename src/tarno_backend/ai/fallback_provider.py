"""Fallback provider that chains multiple LLM providers."""

from __future__ import annotations

import logging
from typing import Any

from tarno_backend.ai.provider import (
    LLMProvider,
    LLMResponse,
    ProviderCapabilities,
    StreamingDelta,
)

log = logging.getLogger(__name__)


class FallbackProvider(LLMProvider):
    """Try a list of providers until one succeeds.

    If the active provider fails, the next provider in the chain is used.
    On success, the active provider is updated so follow-up calls prefer the
    working backend.
    """

    def __init__(self, providers: list[LLMProvider]) -> None:
        if not providers:
            raise ValueError("At least one provider is required for a fallback chain")
        self._providers = list(providers)
        self._current_index = 0

    @property
    def name(self) -> str:
        return "fallback(" + "->".join(p.name for p in self._providers) + ")"

    @property
    def supports_tools(self) -> bool:
        return all(p.supports_tools for p in self._providers)

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            streaming=any(p.capabilities.streaming for p in self._providers),
            tool_calls=self.supports_tools,
        )

    def health_check(self) -> bool:
        return any(p.health_check() for p in self._providers)

    def _try_providers(
        self,
        method: str,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None = None,
        reasoning_effort: str | None = None,
        use_high_tier: bool = False,
    ) -> LLMResponse:
        last_error: Exception | None = None
        start_index = self._current_index

        for offset in range(len(self._providers)):
            idx = (start_index + offset) % len(self._providers)
            provider = self._providers[idx]
            tools_for_provider = tools if provider.supports_tools else None

            try:
                response = getattr(provider, method)(
                    messages=messages,
                    system=system,
                    tools=tools_for_provider,
                )
                self._current_index = idx
                if offset > 0:
                    log.info("Fallback auf Provider '%s' erfolgreich", provider.name)
                return response
            except Exception as exc:
                last_error = exc
                log.warning(
                    "Provider '%s' fehlgeschlagen (%s), probiere naechsten...",
                    provider.name,
                    exc,
                )

        raise last_error or RuntimeError("Alle Provider in der Fallback-Kette fehlgeschlagen")

    def send(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None = None,
        reasoning_effort: str | None = None,
        use_high_tier: bool = False,
    ) -> LLMResponse:
        return self._try_providers("send", messages, system, tools)

    def send_tool_result(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None = None,
        reasoning_effort: str | None = None,
        use_high_tier: bool = False,
    ) -> LLMResponse:
        return self._try_providers("send_tool_result", messages, system, tools)

    def send_stream(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None = None,
    ):
        """Stream deltas from the first provider that supports streaming.

        If no provider in the chain supports streaming, the fallback provider
        calls the synchronous `send` method and yields the whole response as a
        single delta.
        """
        start_index = self._current_index
        last_error: Exception | None = None

        for offset in range(len(self._providers)):
            idx = (start_index + offset) % len(self._providers)
            provider = self._providers[idx]
            if not provider.capabilities.streaming:
                continue
            tools_for_provider = tools if provider.supports_tools else None
            try:
                yield from provider.send_stream(
                    messages=messages,
                    system=system,
                    tools=tools_for_provider,
                )
                self._current_index = idx
                if offset > 0:
                    log.info("Fallback-Streaming auf Provider '%s' erfolgreich", provider.name)
                return
            except Exception as exc:
                last_error = exc
                log.warning(
                    "Provider '%s' streaming fehlgeschlagen, probiere naechsten...",
                    provider.name,
                )

        if last_error is not None:
            log.warning(
                "Kein Streaming-Provider verfuegbar, verwende synchronen Fallback (%s)",
                last_error,
            )
        response = self.send(messages, system, tools)
        yield StreamingDelta(text=response.text, is_finished=True)
