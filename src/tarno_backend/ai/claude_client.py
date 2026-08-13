"""Claude API provider with native tool_use support."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from tarno_backend.ai.provider import LLMProvider, LLMResponse, ToolCall

if TYPE_CHECKING:
    from tarno_backend.core.config import ClaudeConfig

log = logging.getLogger(__name__)


class ClaudeProvider(LLMProvider):
    """Claude API via Anthropic SDK — premium quality, uses API credits."""

    def __init__(self, config: ClaudeConfig, api_key: str = "") -> None:
        # Resolved by the caller (tarno.ai.factory) via SecretsVault, which
        # itself falls back to the ANTHROPIC_API_KEY env var - kept as a
        # direct fallback here too so ClaudeProvider() still works standalone.
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY nicht gesetzt. "
                "Setze die Umgebungsvariable oder nutze provider: ollama in der Config."
            )
        from anthropic import Anthropic
        self._client = Anthropic(
            api_key=api_key,
            timeout=config.timeout,
            max_retries=config.max_retries,
        )
        self._model = config.model
        self._max_tokens = config.max_tokens
        log.info(
            "Claude Provider initialisiert (model=%s, timeout=%.1fs, retries=%d)",
            self._model,
            config.timeout,
            config.max_retries,
        )

    @property
    def name(self) -> str:
        return "claude"

    @property
    def supports_tools(self) -> bool:
        return True

    def send(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None = None,
        reasoning_effort: str | None = None,
        use_high_tier: bool = False,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        log.debug("Claude API call (%d messages, %d tools)", len(messages), len(tools or []))
        response = self._client.messages.create(**kwargs)
        return self._parse(response)

    def send_tool_result(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None = None,
        reasoning_effort: str | None = None,
        use_high_tier: bool = False,
    ) -> LLMResponse:
        return self.send(messages, system, tools)

    @staticmethod
    def _parse(response: Any) -> LLMResponse:
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    input=block.input,
                ))

        return LLMResponse(
            text=" ".join(text_parts),
            tool_calls=tool_calls,
            raw=response,
        )
