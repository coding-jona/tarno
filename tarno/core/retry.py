"""Retry helpers with exponential backoff for TARNO."""

from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable, Iterable, TypeVar

log = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def _calculate_delay(base_delay: float, attempt: int, max_delay: float | None) -> float:
    delay = base_delay * (2 ** attempt)
    if max_delay is not None:
        delay = min(delay, max_delay)
    return delay


def retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float | None = None,
    exceptions: Iterable[type[Exception]] = (Exception,),
    on_retry: Callable[[Exception], None] | None = None,
) -> Callable[[F], F]:
    """Decorator that retries a synchronous callable with exponential backoff."""
    exception_types = tuple(exceptions)

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exception_types as exc:
                    last_exc = exc
                    if attempt >= max_retries:
                        break
                    delay = _calculate_delay(base_delay, attempt, max_delay)
                    log.warning(
                        "%s failed (attempt %d/%d), retry in %.1fs: %s",
                        func.__name__, attempt + 1, max_retries, delay, exc,
                    )
                    if on_retry:
                        on_retry(exc)
                    time.sleep(delay)
            assert last_exc is not None
            raise last_exc

        return wrapper  # type: ignore[return-value]

    return decorator


class AsyncRetry:
    """Class-based async retry helper.

    Python's asyncio.sleep cannot be called inside a synchronous decorator,
    so providers that need async retries can use this helper explicitly.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float | None = None,
        exceptions: Iterable[type[Exception]] = (Exception,),
        on_retry: Callable[[Exception], None] | None = None,
    ) -> None:
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._exceptions = tuple(exceptions)
        self._on_retry = on_retry

    async def run(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except self._exceptions as exc:
                last_exc = exc
                if attempt >= self._max_retries:
                    break
                delay = _calculate_delay(self._base_delay, attempt, self._max_delay)
                log.warning(
                    "Async call failed (attempt %d/%d), retry in %.1fs: %s",
                    attempt + 1, self._max_retries, delay, exc,
                )
                if self._on_retry:
                    self._on_retry(exc)
                import asyncio
                await asyncio.sleep(delay)
        assert last_exc is not None
        raise last_exc
