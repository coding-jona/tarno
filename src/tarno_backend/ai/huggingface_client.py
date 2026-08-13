"""Hugging Face Inference provider — free, no daily request cap, OpenAI-compatible."""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any

from tarno_backend.ai.provider import LLMProvider, LLMResponse, ToolCall

log = logging.getLogger(__name__)

_ROUTER_URL = "https://router.huggingface.co/v1"


class HuggingFaceProvider(LLMProvider):
    """Free cloud LLM via Hugging Face Inference Providers.

    No hard daily request cap — rate-limited per hour instead.
    Routes through multiple providers (Cerebras, Novita, etc.) for redundancy.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "Qwen/Qwen3-32B",
        max_tokens: int = 1024,
        temperature: float = 0.7,
        timeout: float = 60.0,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> None:
        # Resolved by the caller (tarno.ai.factory) via SecretsVault, which
        # itself falls back to the HF_TOKEN env var - kept as a direct
        # fallback here too so HuggingFaceProvider() still works standalone.
        self._api_key = api_key or os.environ.get("HF_TOKEN", "")
        if not self._api_key:
            raise RuntimeError(
                "HF_TOKEN nicht gesetzt. "
                "Erstelle einen kostenlosen Token auf https://huggingface.co/settings/tokens"
            )
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._timeout = timeout
        self._max_retries = max_retries
        self._base_delay = base_delay
        log.info(
            "HuggingFace Provider initialisiert (model=%s, timeout=%.1fs, retries=%d)",
            self._model,
            self._timeout,
            self._max_retries,
        )

    @property
    def name(self) -> str:
        return "huggingface"

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
        oai_messages: list[dict[str, Any]] = [{"role": "system", "content": system}]

        for msg in messages:
            oai_messages.append(self._convert_message(msg))

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": oai_messages,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
        }

        if tools:
            payload["tools"] = self._convert_tools(tools)
            payload["tool_choice"] = "auto"

        return self._call(payload)

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
            f"{_ROUTER_URL}/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "User-Agent": "TARNO-AI/5.0",
            },
        )

        last_attempt = self._max_retries
        for attempt in range(last_attempt + 1):
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    result = json.loads(resp.read())
                return self._parse(result)
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                log.error("HuggingFace API Fehler %d: %s", exc.code, body)
                if exc.code in (429, 402, 500, 501, 502, 503, 504):
                    if attempt < last_attempt:
                        delay = self._base_delay * (2 ** attempt)
                        log.warning("HuggingFace transienter Fehler %d, retry in %.1fs (Versuch %d/%d)", exc.code, delay, attempt + 1, last_attempt)
                        time.sleep(delay)
                        continue
                    if exc.code in (429, 402):
                        return LLMResponse(
                            text="Sir, die HuggingFace Credits sind erschöpft. "
                                 "Wechseln Sie den Provider oder warten Sie bis zum nächsten Monat.",
                            tool_calls=[],
                            is_error=True,
                        )
                    if exc.code == 503:
                        return LLMResponse(
                            text="Das Modell wird gerade geladen. Bitte versuchen Sie es in wenigen Sekunden erneut.",
                            tool_calls=[],
                            is_error=True,
                        )
                return LLMResponse(text=f"HuggingFace API Fehler: {exc.code}", tool_calls=[], is_error=True)
            except urllib.error.URLError as exc:
                log.error("HuggingFace nicht erreichbar: %s", exc)
                if attempt < last_attempt:
                    delay = self._base_delay * (2 ** attempt)
                    log.warning("HuggingFace Netzwerkfehler, retry in %.1fs (Versuch %d/%d)", delay, attempt + 1, last_attempt)
                    time.sleep(delay)
                    continue
                return LLMResponse(text="HuggingFace API nicht erreichbar.", tool_calls=[], is_error=True)

        return LLMResponse(text="HuggingFace API nicht erreichbar.", tool_calls=[], is_error=True)

    @staticmethod
    def _convert_message(msg: dict[str, Any]) -> dict[str, Any]:
        content = msg.get("content", "")
        role = msg.get("role", "user")

        if isinstance(content, str):
            return {"role": role, "content": content}

        if isinstance(content, list):
            parts: list[str] = []
            tool_results: list[dict[str, Any]] = []

            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    parts.append(block["text"])
                elif block.get("type") == "tool_result":
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": block["tool_use_id"],
                        "content": block.get("content", ""),
                    })
                elif block.get("type") == "tool_use":
                    return {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": block["id"],
                            "type": "function",
                            "function": {
                                "name": block["name"],
                                "arguments": json.dumps(block["input"]),
                            },
                        }],
                    }

            if tool_results:
                return tool_results[0]

            return {"role": role, "content": " ".join(parts) if parts else str(content)}

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

    @staticmethod
    def _parse(result: dict[str, Any]) -> LLMResponse:
        choice = result.get("choices", [{}])[0]
        message = choice.get("message", {})
        text = message.get("content", "") or ""
        tool_calls: list[ToolCall] = []

        for tc in (message.get("tool_calls") or []):
            fn = tc.get("function", {})
            args = fn.get("arguments", "{}")
            try:
                parsed_args = json.loads(args)
            except json.JSONDecodeError:
                parsed_args = {}
            tool_calls.append(ToolCall(
                id=tc.get("id", ""),
                name=fn.get("name", ""),
                input=parsed_args,
            ))

        text = re.sub(r"<think>[\s\S]*?</think>", "", text)
        text = re.sub(r"<\|Start of tool call\|>[\s\S]*?<\|End of tool call\|>", "", text)
        text = re.sub(r"```tool_code[\s\S]*?```", "", text)
        text = text.strip()
        return LLMResponse(text=text, tool_calls=tool_calls, raw=result)
