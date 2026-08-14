"""Abstract LLM provider interface."""

from __future__ import annotations

import logging
import re
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
    is_finished: bool = False
    is_error: bool = False


@dataclass
class ToolCall:
    """A single tool invocation requested by the LLM."""
    id: str
    name: str
    input: dict[str, Any]
    # Opaque provider-specific metadata that MUST be echoed back verbatim on
    # the next call for that same provider (e.g. Gemini's thought_signature,
    # https://ai.google.dev/gemini-api/docs/thought-signatures) - without it,
    # the provider rejects its own historical function call on replay. None
    # for providers that need nothing extra. Other providers reading the
    # same shared conversation history simply ignore this key.
    raw_extra: dict[str, Any] | None = None


def extract_reasoning(text: str) -> tuple[str, str | None]:
    """Splits off a <think>...</think> block instead of just discarding it
    (the previous behavior in every provider client). Returns (visible_text,
    reasoning_or_None)."""
    match = re.search(r"<think>([\s\S]*?)</think>", text)
    if not match:
        return text.strip(), None
    reasoning = match.group(1).strip()
    visible = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
    return visible, reasoning or None


class LLMProvider(ABC):
    """Base class for all LLM backends."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def supports_tools(self) -> bool: ...

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Provider capability flags."""
        return ProviderCapabilities(tool_calls=self.supports_tools)

    @abstractmethod
    def send(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None = None,
        reasoning_effort: str | None = None,
        use_high_tier: bool = False,
    ) -> LLMResponse: ...

    @abstractmethod
    def send_tool_result(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None = None,
        reasoning_effort: str | None = None,
        use_high_tier: bool = False,
    ) -> LLMResponse: ...

    def send_stream(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None = None,
        reasoning_effort: str | None = None,
        use_high_tier: bool = False,
    ) -> Iterator[StreamingDelta]:
        """Default streaming implementation: not supported."""
        raise NotImplementedError(f"{self.name} does not support streaming")

    def health_check(self) -> bool:
        """Return True if the provider appears to be usable.

        Subclasses may override this with a lightweight readiness check.
        """
        return True

    @staticmethod
    def _retry_after_delay(exc: urllib.error.HTTPError, default: float, max_delay: float) -> float:
        """Read Retry-After header from a 429 HTTPError and cap it."""
        headers = getattr(exc, "headers", None)
        if headers:
            retry_after = headers.get("Retry-After") or headers.get("retry-after")
            if retry_after:
                try:
                    return min(max(float(retry_after), 0.5), max_delay)
                except (ValueError, TypeError):
                    pass
        return min(default, max_delay)

    def _http_request_with_retry(
        self,
        req: urllib.request.Request,
        timeout: float = 60.0,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        max_429_attempts: int = 12,
    ) -> Any:
        """Open a urllib request and retry on 429/5xx/transient network errors.

        For 429 (rate limit) we keep trying for longer with exponential
        backoff or Retry-After header values. 5xx and network errors only get
        the configured max_retries. Raises the last error if all retries fail.
        """
        attempts_429 = 0
        attempts_other = 0
        rate_limiter = getattr(self, "_rate_limiter", None)
        if rate_limiter is not None:
            rate_limiter.acquire()
        while True:
            try:
                return urllib.request.urlopen(req, timeout=timeout)
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    if attempts_429 >= max_429_attempts:
                        raise
                    delay = self._retry_after_delay(exc, base_delay * (2 ** attempts_429), max_delay)
                    log.warning("API 429 Rate-Limit, warte %.1fs vor Wiederholung (%d/%d)", delay, attempts_429 + 1, max_429_attempts)
                    time.sleep(delay)
                    attempts_429 += 1
                    continue
                if 500 <= exc.code < 600:
                    if attempts_other >= max_retries:
                        raise
                    delay = min(base_delay * (2 ** attempts_other), max_delay)
                    log.warning("API %d, retry in %.1fs (%d/%d)", exc.code, delay, attempts_other + 1, max_retries)
                    time.sleep(delay)
                    attempts_other += 1
                    continue
                raise
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempts_other >= max_retries:
                    raise
                delay = min(base_delay * (2 ** attempts_other), max_delay)
                log.warning("Netzwerkfehler, retry in %.1fs (%d/%d): %s", delay, attempts_other + 1, max_retries, exc)
                time.sleep(delay)
                attempts_other += 1
                continue
