"""Abstract LLM provider interface."""

from __future__ import annotations

import logging
import threading
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterator

log = logging.getLogger(__name__)


class RateLimiter:
    """Simple token-bucket-style rate limiter enforcing max requests per second."""

    def __init__(self, max_rps: float) -> None:
        self._min_interval = 1.0 / max_rps if max_rps and max_rps > 0 else 0.0
        self._last = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> None:
        if self._min_interval <= 0.0:
            return
        with self._lock:
            elapsed = time.monotonic() - self._last
            wait = self._min_interval - elapsed
            if wait > 0.0:
                time.sleep(wait)
            self._last = time.monotonic()

# Shared across every provider client's outbound HTTP requests. Python's
# urllib default ("Python-urllib/3.x") is a signature some WAFs (including
# Cloudflare, observed live via a Groq 403 "browser signature banned") block
# outright, independent of a valid API key - a real, plain HTTP request
# identifies its client honestly instead of leaving the stdlib default.
REQUEST_USER_AGENT = "TARNO-Assistant/0.6"


@dataclass
class LLMResponse:
    """Unified response from any LLM provider."""
    text: str
    tool_calls: list[ToolCall]
    raw: Any = None
    # Context-window usage for this turn, if the provider reports it (e.g.
    # Mistral's usage.total_tokens) - used to drive a token-usage indicator
    # in the UI. None when unavailable (provider doesn't report it, or the
    # call failed before a response was parsed).
    tokens_used: int | None = None
    context_window: int | None = None
    # True when this response is a synthetic error placeholder (rate limit
    # exhausted, API error, network unreachable) rather than a real model
    # answer - lets callers react (e.g. flash the Voice-Orb to "error")
    # without having to string-match response text.
    is_error: bool = False
    # Captured <think>...</think> content, if the model produced any - was
    # previously stripped and discarded by every provider client; now
    # surfaced so the UI can show it as a genuine reasoning trace instead of
    # a fake "Denkt nach..." placeholder. None when no reasoning was present.
    reasoning: str | None = None


@dataclass
class ProviderCapabilities:
    """Describes which optional features a provider supports."""

    streaming: bool = False
    tool_calls: bool = False
    async_support: bool = False
    # True only for providers/models that support a structured "thinking
    # harder" request (currently: Mistral's magistral-* models via
    # reasoning_effort). Distinct from the reasoning field on LLMResponse,
    # which just captures whatever a model volunteers unprompted for free.
    reasoning_effort: bool = False


@dataclass
class StreamingDelta:
    """A single incremental piece of a streaming response."""

    text: str = ""
    tool_call: ToolCall | None = None
