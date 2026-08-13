"""Abstract base class for coding adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Iterator

from tarno.ai.coding.protocol import CodingOutput

OnOutput = Callable[[CodingOutput], None]


class CodingBackend(ABC):
    """Base class for a concrete coding-agent integration."""

    @abstractmethod
    def run(
        self,
        prompt: str,
        workspace: dict[str, Any],
        fnames: list[str],
        read_only: bool,
        on_output: OnOutput | None = None,
    ) -> Iterator[CodingOutput]:
        """Execute the coding prompt and yield final/summary outputs.

        The ``on_output`` callback is invoked for every live progress chunk
        so callers can stream it to the UI before the generator finishes.
        """
        ...
