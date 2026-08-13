"""Bridges Python logging records into the Qt main thread for GUI display."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal


class QtLogHandler(logging.Handler, QObject):
    """A logging.Handler that emits a Qt signal for each log record.

    Safe to attach to the root logger even though records may originate on
    worker threads — Qt automatically queues the signal delivery onto the
    thread this QObject lives on (the GUI main thread)."""

    log_emitted = Signal(str)

    def __init__(self, level: int = logging.INFO) -> None:
        logging.Handler.__init__(self, level=level)
        QObject.__init__(self)
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
        except Exception:
            return
        self.log_emitted.emit(msg)
