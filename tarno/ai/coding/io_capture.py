"""Output capture that forwards aider progress into TARNO events."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from tarno.ai.coding.protocol import CodingOutput

try:
    from aider.io import InputOutput as _AiderInputOutput
except ImportError:  # pragma: no cover - aider is optional until installed
    _AiderInputOutput = object

log = logging.getLogger(__name__)

OnOutput = Callable[[CodingOutput], None]


class _NullMdStream:
    """Drop-in for aider's MarkdownStream when live rendering isn't needed."""

    def __call__(self, *args: Any, **kwargs: Any) -> "_NullMdStream":
        return self

    def __getattr__(self, name: str) -> Any:
        return lambda *args, **kwargs: None


class TarnoInputOutput(_AiderInputOutput):
    """aider I/O subclass that streams progress as ``CodingOutput`` events.

    Inherits the full aider ``InputOutput`` surface so ``Coder.create`` has all
    attributes it expects.  Autonomous output methods are redirected into the
    optional ``on_output`` callback; interactive methods are no-ops.
    """

    def __init__(self, on_output: OnOutput | None = None) -> None:
        # Store callback before super().__init__ because the base init already
        # calls tool_output()/append_chat_history() and we want to catch those.
        self._tarno_on_output = on_output
        self._last_text = ""
        super().__init__(
            pretty=False,
            fancy_input=False,
            notifications=False,
        )

    def _emit(self, kind: str, text: str) -> None:
        if not self._tarno_on_output or not text:
            return
        if kind == "text" and text == self._last_text:
            return
        if kind == "text":
            self._last_text = text
        try:
            self._tarno_on_output(
                CodingOutput(
                    kind=kind,
                    text=text,
                    timestamp_ms=int(time.monotonic() * 1000),
                )
            )
        except Exception:
            log.exception("Coding-Output-Callback fehlgeschlagen")

    def tool_output(self, text: str = "", *args: Any, **kwargs: Any) -> None:
        self._emit("text", text)

    def tool_warning(self, text: str = "", *args: Any, **kwargs: Any) -> None:
        self._emit("text", f"Warnung: {text}")

    def tool_error(self, text: str = "", *args: Any, **kwargs: Any) -> None:
        self._emit("error", text)

    def assistant_output(self, text: str = "", *args: Any, **kwargs: Any) -> None:
        self._emit("text", text)

    def ai_output(self, content: str = "", *args: Any, **kwargs: Any) -> None:
        self._emit("text", content)

    def append_chat_history(self, *args: Any, **kwargs: Any) -> None:
        """Disable file-based chat history in the autonomous flow."""
        return

    def user_input(self, inp: str = "", *args: Any, **kwargs: Any) -> None:
        """Disable user input prompts; the prompt is already known to the agent."""
        self._emit("user", inp)

    def get_input(self, *args: Any, **kwargs: Any) -> str:
        """No interactive input in autonomous mode."""
        return ""

    def get_assistant_mdstream(self, *args: Any, **kwargs: Any) -> _NullMdStream:
        return _NullMdStream()

    def read_text(self, *args: Any, **kwargs: Any) -> str:
        """aider may ask for user input; in autonomous mode we return nothing."""
        return ""

    def prompt(self, *args: Any, **kwargs: Any) -> str:
        """Disable interactive prompts in the autonomous coding flow."""
        return ""

    def prompt_ask(self, *args: Any, **kwargs: Any) -> str:
        """Disable interactive prompts in the autonomous coding flow."""
        return ""

    def confirm_ask(self, *args: Any, **kwargs: Any) -> bool:
        """Disable confirmations in the autonomous coding flow."""
        return False

    def offer_url(self, *args: Any, **kwargs: Any) -> None:
        return
