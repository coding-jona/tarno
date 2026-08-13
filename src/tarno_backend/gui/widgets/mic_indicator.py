"""Microphone toggle button with state indicator."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton, QWidget

from tarno_backend.gui.theme import COLORS


class MicIndicator(QPushButton):
    """Circular mic button: gray=off, blue=listening, green=recognized."""

    toggled_voice = Signal(bool)

    _STATE_COLORS = {
        "off": COLORS["text_muted"],
        "listening": COLORS["brand_500"],
        "recognized": COLORS["success"],
        "error": COLORS["error"],
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("\U0001F3A4", parent)
        self.setObjectName("micButton")
        self._active = False
        self._state = "off"
        self.clicked.connect(self._on_click)

    @property
    def active(self) -> bool:
        return self._active

    def set_state(self, state: str) -> None:
        self._state = state
        self._active = state != "off"
        self.setProperty("active", str(self._active).lower())
        self.style().unpolish(self)
        self.style().polish(self)

    def _on_click(self) -> None:
        self._active = not self._active
        if self._active:
            self.set_state("listening")
        else:
            self.set_state("off")
        self.toggled_voice.emit(self._active)
