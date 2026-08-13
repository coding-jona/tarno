"""Console-based user interface."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tarno.core.events import (
    ErrorEvent,
    EventBus,
    ResponseReadyEvent,
    SpeechRecognizedEvent,
    StreamingDeltaEvent,
    StreamingFinishedEvent,
    WakeWordDetectedEvent,
)

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

_BANNER = r"""
╔══════════════════════════════════════════════════════════════════╗
║               TARNO AI Assistant v5.0                         ║
║         Intelligent Desktop Agent · Inspired by Iron Man       ║
╠══════════════════════════════════════════════════════════════════╣
║  Sage "Hey Tarno" oder "Tarno" zum Aktivieren                ║
║  Beenden: "Exit" / "Auf Wiedersehen" / Ctrl+C                  ║
╚══════════════════════════════════════════════════════════════════╝
"""


class ConsoleUI:
    """Subscribes to events and renders them to the terminal."""

    def __init__(self, event_bus: EventBus, text_mode: bool = False) -> None:
        self._text_mode = text_mode
        self._stream_buffer = ""
        event_bus.subscribe(WakeWordDetectedEvent, self._on_wakeword)
        event_bus.subscribe(SpeechRecognizedEvent, self._on_speech)
        event_bus.subscribe(ResponseReadyEvent, self._on_response)
        event_bus.subscribe(StreamingDeltaEvent, self._on_streaming_delta)
        event_bus.subscribe(StreamingFinishedEvent, self._on_streaming_finished)
        event_bus.subscribe(ErrorEvent, self._on_error)

    @staticmethod
    def show_banner() -> None:
        print(_BANNER)

    @staticmethod
    def _on_wakeword(event: WakeWordDetectedEvent) -> None:
        print("\n--- Wake word erkannt ---")

    def _on_speech(self, event: SpeechRecognizedEvent) -> None:
        if not self._text_mode:
            print(f"\n  Sie: {event.text}")

    @staticmethod
    def _on_response(event: ResponseReadyEvent) -> None:
        print(f"\n  TARNO: {event.text}")

    def _on_streaming_delta(self, event: StreamingDeltaEvent) -> None:
        if not event.text:
            return
        if not self._stream_buffer:
            print("\n  TARNO: ", end="", flush=True)
        self._stream_buffer += event.text
        print(event.text, end="", flush=True)
        if event.is_finished:
            print()
            self._stream_buffer = ""

    def _on_streaming_finished(self, event: StreamingFinishedEvent) -> None:
        if not self._stream_buffer:
            return
        print(f"\n  TARNO: {self._stream_buffer}")
        self._stream_buffer = ""

    @staticmethod
    def _on_error(event: ErrorEvent) -> None:
        print(f"\n  [Fehler in {event.module}]: {event.error}")
