"""Engine controller running the OVOS engine in a QThread."""

from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, QThread, Signal
from ovos_bus_client.message import Message

from tarno_backend.core.ovos_engine import TarnoOvosEngine

log = logging.getLogger(__name__)


class EngineController(QObject):
    """Wraps the OVOS engine in a QThread and exposes control slots."""

    engine_started = Signal()
    engine_stopped = Signal()
    error_occurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._engine: TarnoOvosEngine | None = None
        self._thread: QThread | None = None
        self._worker: _EngineWorker | None = None
        self._shutdown_event = threading.Event()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def start_engine(self) -> None:
        if self.is_running():
            return

        self._thread = QThread()
        self._worker = _EngineWorker(self._shutdown_event)
        self._worker.moveToThread(self._thread)
        self._worker.started.connect(self.engine_started.emit)
        self._worker.stopped.connect(self.engine_stopped.emit)
        self._worker.error.connect(self.error_occurred.emit)
        self._thread.started.connect(self._worker.run)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.start()

    def stop_engine(self) -> None:
        if self._worker is not None:
            self._worker.stop()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(5000)

    def send_text(self, text: str, language: str = "de") -> None:
        if self._worker is None or self._worker.engine is None:
            return
        bus = self._worker.engine._bus_client
        if bus is None:
            return
        message = Message(
            "recognizer_loop:utterance",
            data={"utterances": [text], "lang": language},
        )
        bus.emit(message)

    def toggle_mute(self, muted: bool) -> None:
        if self._worker is None or self._worker.engine is None:
            return
        voice_service = self._worker.engine._voice_service
        if voice_service is None:
            return
        if muted:
            voice_service.stop()
        else:
            voice_service.start()


class _EngineWorker(QObject):
    """Runs the OVOS engine in a QThread."""

    started = Signal()
    stopped = Signal()
    error = Signal(str)

    def __init__(self, shutdown_event: threading.Event) -> None:
        super().__init__()
        self._shutdown_event = shutdown_event
        self.engine: TarnoOvosEngine | None = None

    def run(self) -> None:
        try:
            self.engine = TarnoOvosEngine()
            self.engine.start()
            self._shutdown_event.clear()
            self.started.emit()
            self._shutdown_event.wait()
        except Exception as exc:
            log.exception("Engine-Fehler")
            self.error.emit(str(exc))
        finally:
            if self.engine is not None:
                self.engine.stop()
            self.stopped.emit()

    def stop(self) -> None:
        self._shutdown_event.set()
