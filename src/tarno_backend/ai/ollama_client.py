"""Ollama provider — free, local, no API limits."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

from tarno_backend.ai.provider import LLMProvider, LLMResponse, ToolCall, extract_reasoning

log = logging.getLogger(__name__)

_DEFAULT_URL = "http://localhost:11434"


def list_ollama_models(base_url: str = _DEFAULT_URL, timeout: float = 5.0) -> list[str]:
    """Queries the local Ollama server's own model list (`/api/tags`) - used
    by the WinUI model picker (Phase 6) instead of a static catalog, since
    which models are available is entirely up to what the user has pulled
    locally. Returns an empty list (not an exception) if Ollama isn't
    reachable, so the picker can show "keine lokalen Modelle gefunden"
    instead of failing the whole GetModelCatalog RPC over one provider."""
    try:
        req = urllib.request.Request(f"{base_url.rstrip('/')}/api/tags")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            return [m["name"] for m in data.get("models", [])]
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
        return []


class OllamaProvider(LLMProvider):
    """Local LLM via Ollama — no API credits, fully offline."""

    def __init__(
        self,
        model: str = "qwen3:8b",
        base_url: str = _DEFAULT_URL,
        num_ctx: int = 8192,
        num_gpu: int = -1,
        temperature: float = 0.7,
        timeout: float = 60.0,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._num_ctx = num_ctx
        self._num_gpu = num_gpu
        self._temperature = temperature
        self._timeout = timeout
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._verify_connection()
        log.info(
            "Ollama Provider initialisiert (model=%s, ctx=%d, gpu_layers=%d, timeout=%.1fs, retries=%d)",
            self._model, self._num_ctx, self._num_gpu, self._timeout, self._max_retries,
        )

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def supports_tools(self) -> bool:
        return True

    def _verify_connection(self) -> None:
        try:
            req = urllib.request.Request(f"{self._base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read())
                models = [m["name"].split(":")[0] for m in data.get("models", [])]
                if self._model not in models and f"{self._model}:latest" not in [m["name"] for m in data.get("models", [])]:
                    available = ", ".join(models) if models else "keine"
                    log.warning(
                        "Modell '%s' nicht gefunden. Verfügbar: %s. "
                        "Installiere mit: ollama pull %s",
                        self._model, available, self._model,
                    )
        except (urllib.error.URLError, OSError):
            raise RuntimeError(
                "Ollama nicht erreichbar. Starte Ollama mit 'ollama serve' "
                "oder installiere es von https://ollama.com"
            )

    def send(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None = None,
        reasoning_effort: str | None = None,
        use_high_tier: bool = False,
    ) -> LLMResponse:
        ollama_messages = [{"role": "system", "content": system}]

        for msg in messages:
            ollama_messages.append(self._convert_message(msg))

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "num_ctx": self._num_ctx,
                "num_gpu": self._num_gpu,
                "temperature": self._temperature,
            },
        }

        if tools:
            payload["tools"] = self._convert_tools(tools)

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self._base_url}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
        )

        last_attempt = self._max_retries
        for attempt in range(last_attempt + 1):
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    result = json.loads(resp.read())
                return self._parse(result)
            except urllib.error.URLError as exc:
                log.error("Ollama Fehler: %s", exc)
                if attempt < last_attempt:
                    delay = self._base_delay * (2 ** attempt)
                    log.warning("Ollama Netzwerkfehler, retry in %.1fs (Versuch %d/%d)", delay, attempt + 1, last_attempt)
                    time.sleep(delay)
                    continue
                return LLMResponse(text="Ollama ist nicht erreichbar.", tool_calls=[], is_error=True)

        return LLMResponse(text="Ollama ist nicht erreichbar.", tool_calls=[], is_error=True)

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
    def _convert_message(msg: dict[str, Any]) -> dict[str, Any]:
        content = msg.get("content", "")

        if isinstance(content, str):
            return {"role": msg["role"], "content": content}

        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(block["text"])
                    elif block.get("type") == "tool_result":
                        parts.append(f"[Tool-Ergebnis]: {block.get('content', '')}")
                    elif block.get("type") == "tool_use":
                        parts.append(f"[Tool-Aufruf: {block.get('name', '')}]")
            return {"role": msg["role"], "content": " ".join(parts) if parts else str(content)}

        return {"role": msg["role"], "content": str(content)}

    @staticmethod
    def _convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ollama_tools = []
        for tool in tools:
            ollama_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                },
            })
        return ollama_tools

    @staticmethod
    def _parse(result: dict[str, Any]) -> LLMResponse:
        message = result.get("message", {})
        text = message.get("content", "")
        tool_calls: list[ToolCall] = []

        for i, tc in enumerate((message.get("tool_calls") or [])):
            fn = tc.get("function", {})
            tool_calls.append(ToolCall(
                id=f"ollama_{i}",
                name=fn.get("name", ""),
                input=fn.get("arguments", {}),
            ))

        text, reasoning = extract_reasoning(text)
        return LLMResponse(text=text, tool_calls=tool_calls, raw=result, reasoning=reasoning)
