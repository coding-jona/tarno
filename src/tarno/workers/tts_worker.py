"""Background thread for text-to-speech synthesis."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from PySide6.QtCore import QObject, Signal, Slot

if TYPE_CHECKING:
    from tarno.voice.synthesizer import SpeechSynthesizer

log = logging.getLogger(__name__)


class TTSWorker(QObject):
    """Runs TTS on a dedicated thread so the GUI stays responsive."""

    speaking_started = Signal()
    speaking_finished = Signal()

    def __init__(
        self,
        synthesizer: "SpeechSynthesizer",
        on_start: Callable[[], None] | None = None,
        on_finish: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self._synthesizer = synthesizer
        self._on_start = on_start
        self._on_finish = on_finish

    @Slot(str)
    def speak(self, text: str) -> None:
        if not text:
            return
        self.speaking_started.emit()
        if self._on_start:
            try:
                self._on_start()
            except Exception:
                log.exception("TTS on_start callback failed")
        try:
            self._synthesizer.speak(text)
        except Exception:
            log.exception("TTS-Fehler")
        if self._on_finish:
            try:
                self._on_finish()
            except Exception:
                log.exception("TTS on_finish callback failed")
        self.speaking_finished.emit()

    @Slot()
    def play_sound(self) -> None:
        """Play the short confirmation sound without emitting TTS signals."""
        try:
            self._synthesizer.play_sound()
        except Exception:
            log.exception("Bestätigungston-Fehler")
