"""Generic OpenAI-compatible chat-completions provider.

Supports any provider that exposes a `/chat/completions` endpoint compatible
with the OpenAI REST contract (OpenAI, GLM, Perplexity, Meta, DeepSeek,
Moonshot/Kimi, Qwen, OpenRouter, ...).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import string
import urllib.error
import urllib.request
from typing import Any, Iterator

from tarno_backend.ai.provider import (
    REQUEST_USER_AGENT,
    LLMProvider,
    LLMResponse,
    ProviderCapabilities,
    RateLimiter,
    StreamingDelta,
    ToolCall,
    extract_reasoning,
)

log = logging.getLogger(__name__)

# Some providers reject tool-call ids that are too short/long or contain
# characters outside [a-zA-Z0-9]. We normalize every incoming/outgoing id to a
# deterministic 9-character alphanumeric string so the same original id always
# maps to the same sanitized id on both tool_use and tool_result sides.
_VALID_TOOL_CALL_ID = re.compile(r"^[a-zA-Z0-9]{9}$")


def _sanitize_tool_call_id(raw_id: str) -> str:
    if _VALID_TOOL_CALL_ID.match(raw_id or ""):
        return raw_id
    digest = hashlib.sha256((raw_id or "").encode("utf-8")).hexdigest()
    alphabet = string.ascii_letters + string.digits
    return "".join(alphabet[int(digest[i * 2:i * 2 + 2], 16) % len(alphabet)] for i in range(9))


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI-compatible LLM backend.

    Parameters are passed in by the factory from `config.llm.openai_compatible`.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        provider_name: str = "openai",
        max_tokens: int = 1024,
        temperature: float = 0.7,
        timeout: float = 60.0,
        max_retries: int = 3,
        base_delay: float = 1.0,
        rate_limit_rps: float = 0.0,
        context_window: int = 128_000,
    ) -> None:
        if not api_key:
            raise RuntimeError(
                f"API-Key für {provider_name} ist nicht gesetzt. "
                f"Lege ihn als Umgebungsvariable an und starte TARNO neu."
            )
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._provider_name = provider_name
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._timeout = timeout
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._context_window = context_window
        self._rate_limiter = RateLimiter(rate_limit_rps) if rate_limit_rps and rate_limit_rps > 0 else None
        log.info(
            "OpenAI-kompatibler Provider initialisiert (%s, model=%s, timeout=%.1fs)",
            provider_name,
            model,
            timeout,
        )

    @property
    def name(self) -> str:
        return self._provider_name

    @property
    def supports_tools(self) -> bool:
        return True

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(streaming=True, tool_calls=True)

    def _build_payload(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        oai_messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for msg in messages:
            oai_messages.append(self._convert_message(msg))

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": oai_messages,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
            "stream": stream,
        }
        if tools:
            payload["tools"] = self._convert_tools(tools)
            payload["tool_choice"] = "auto"
        return payload

    def send(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None = None,
        reasoning_effort: str | None = None,
        use_high_tier: bool = False,
    ) -> LLMResponse:
        payload = self._build_payload(messages, system, tools, stream=False)
        return self._call(payload)

    def send_stream(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None = None,
        reasoning_effort: str | None = None,
        use_high_tier: bool = False,
    ) -> Iterator[StreamingDelta]:
        payload = self._build_payload(messages, system, tools, stream=True)
        yield from self._call_stream(payload)

    def send_tool_result(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None = None,
        reasoning_effort: str | None = None,
        use_high_tier: bool = False,
    ) -> LLMResponse:
        return self.send(messages, system, tools)

    def _call(self, payload: dict[str, Any]) -> LLMResponse:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "User-Agent": REQUEST_USER_AGENT,
            },
        )
        try:
            with self._http_request_with_retry(
                req,
                timeout=self._timeout,
                max_retries=self._max_retries,
                base_delay=self._base_delay,
            ) as resp:
                result = json.loads(resp.read())
            return self._parse(result)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            log.error("%s API Fehler %d: %s", self._provider_name, exc.code, body)
            if exc.code == 429:
                return LLMResponse(
                    text=f"Sir, das Rate-Limit für {self._provider_name} ist aktiv. Bitte warten Sie einen Moment.",
                    tool_calls=[],
                    is_error=True,
                )
            return LLMResponse(text=f"{self._provider_name} API Fehler: {exc.code}", tool_calls=[], is_error=True)
        except (urllib.error.URLError, TimeoutError) as exc:
            log.error("%s nicht erreichbar: %s", self._provider_name, exc)
            return LLMResponse(text=f"{self._provider_name} API nicht erreichbar.", tool_calls=[], is_error=True)

    def _call_stream(self, payload: dict[str, Any]) -> Iterator[StreamingDelta]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "User-Agent": REQUEST_USER_AGENT,
                "Accept": "text/event-stream",
            },
        )
        try:
            with self._http_request_with_retry(
                req,
                timeout=self._timeout,
                max_retries=self._max_retries,
                base_delay=self._base_delay,
            ) as resp:
                text_parts: list[str] = []
                tool_acc: dict[int, dict[str, Any]] = {}
                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if not line.startswith("data:"):
                        continue
                    data_payload = line[5:].strip()
                    if data_payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_payload)
                    except json.JSONDecodeError:
                        continue
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    if delta.get("content"):
                        text_parts.append(delta["content"])
                        yield StreamingDelta(text=delta["content"])
                    for tc in delta.get("tool_calls") or []:
                        idx = tc.get("index", 0)
                        if idx not in tool_acc:
                            tool_acc[idx] = {
                                "id": _sanitize_tool_call_id(tc.get("id") or ""),
                                "type": tc.get("type", "function"),
                                "function": {"name": "", "arguments": ""},
                            }
                        func = tc.get("function", {})
                        if func.get("name"):
                            tool_acc[idx]["function"]["name"] = func["name"]
                        if func.get("arguments"):
                            tool_acc[idx]["function"]["arguments"] += func["arguments"]
                for idx in sorted(tool_acc):
                    tool = tool_acc[idx]
                    name = tool["function"].get("name", "")
                    try:
                        args = json.loads(tool["function"].get("arguments", "{}"))
                    except json.JSONDecodeError:
                        args = {}
                    yield StreamingDelta(
                        tool_call=ToolCall(id=tool["id"], name=name, input=args),
                    )
                visible = "".join(text_parts)
                visible, reasoning = extract_reasoning(visible)
                yield StreamingDelta(is_finished=True)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            log.error("%s Streaming Fehler %d: %s", self._provider_name, exc.code, body)
            yield StreamingDelta(text=f"{self._provider_name} API Fehler: {exc.code}", is_finished=True, is_error=True)
        except (urllib.error.URLError, TimeoutError) as exc:
            log.error("%s Streaming nicht erreichbar: %s", self._provider_name, exc)
            yield StreamingDelta(text=f"{self._provider_name} API nicht erreichbar.", is_finished=True, is_error=True)

    @staticmethod
    def _convert_message(msg: dict[str, Any]) -> dict[str, Any]:
        content = msg.get("content", "")
        role = msg.get("role", "user")

        if isinstance(content, str):
            if role == "assistant" and not content:
                content = "..."
            return {"role": role, "content": content}

        if isinstance(content, list):
            text_parts: list[str] = []
            image_blocks: list[dict[str, Any]] = []
            tool_results: list[dict[str, Any]] = []
            tool_calls: list[dict[str, Any]] = []

            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    text_parts.append(block["text"])
                elif block.get("type") == "image_url":
                    image_blocks.append(block)
                elif block.get("type") == "tool_result":
                    tool_content = block.get("content", "")
                    if not isinstance(tool_content, str):
                        tool_content = json.dumps(tool_content, ensure_ascii=False)
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": _sanitize_tool_call_id(block["tool_use_id"]),
                        "content": tool_content,
                    })
                elif block.get("type") == "tool_use":
                    tool_calls.append({
                        "id": _sanitize_tool_call_id(block["id"]),
                        "type": "function",
                        "function": {
                            "name": block["name"],
                            "arguments": json.dumps(block["input"]),
                        },
                    })

            if tool_calls:
                return {
                    "role": "assistant",
                    "content": " ".join(text_parts) if text_parts else "",
                    "tool_calls": tool_calls,
                }

            if tool_results:
                return tool_results[0]

            if image_blocks:
                parts: list[dict[str, Any]] = []
                if text_parts:
                    parts.append({"type": "text", "text": " ".join(text_parts)})
                parts.extend(image_blocks)
                return {"role": role, "content": parts}

            joined = " ".join(text_parts) if text_parts else str(content)
            if role == "assistant" and not joined.strip():
                joined = "..."
            return {"role": role, "content": joined}

        return {"role": role, "content": str(content)}

    @staticmethod
    def _convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {}),
                },
            }
            for t in tools
        ]

    def _parse(self, result: dict[str, Any]) -> LLMResponse:
        choice = result.get("choices", [{}])[0]
        message = choice.get("message", {})
        raw_content = message.get("content", "") or ""
        if isinstance(raw_content, list):
            raw_content = " ".join(
                str(b.get("text", b)) for b in raw_content if isinstance(b, dict)
            )
        visible, reasoning = extract_reasoning(raw_content.strip())

        tool_calls: list[ToolCall] = []
        for tc in message.get("tool_calls", []):
            func = tc.get("function", {})
            name = func.get("name", "")
            try:
                args = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(
                id=_sanitize_tool_call_id(tc.get("id", "")),
                name=name,
                input=args,
            ))

        usage = result.get("usage", {})
        tokens_used = usage.get("total_tokens") or usage.get("prompt_tokens") or None

        return LLMResponse(
            text=visible,
            tool_calls=tool_calls,
            tokens_used=tokens_used,
            context_window=self._context_window,
            reasoning=reasoning,
        )
