"""Transparent TARNO overlay window for desktop status feedback.

The overlay is a frameless, always-on-top window that shows a pulsing status
orb and short status messages. It is designed to look like a holographic HUD
element without blocking user interaction with other applications.
"""

from __future__ import annotations

import logging
from enum import Enum

from PySide6.QtCore import QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QRadialGradient
from PySide6.QtWidgets import QApplication, QLabel, QWidget

log = logging.getLogger(__name__)


class OverlayState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    WARNING = "warning"


_STATE_COLORS: dict[OverlayState, QColor] = {
    OverlayState.IDLE: QColor(0, 160, 255),
    OverlayState.LISTENING: QColor(0, 220, 120),
    OverlayState.THINKING: QColor(255, 180, 0),
    OverlayState.SPEAKING: QColor(180, 100, 255),
    OverlayState.WARNING: QColor(255, 60, 60),
}


class OverlayWindow(QWidget):
    """A lightweight, click-through capable overlay HUD."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(180, 180)
        self._state = OverlayState.IDLE
        self._pulse = 0.0
        self._color = _STATE_COLORS[self._state]

        self._status_label = QLabel("Bereit", self)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._status_label.setStyleSheet("color: rgba(200, 230, 255, 220);")
        self._status_label.setGeometry(20, 130, 140, 30)

        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._step_pulse)
        self._pulse_timer.start(40)

        self._animation = QPropertyAnimation(self, b"windowOpacity")
        self._animation.setDuration(300)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self.setWindowOpacity(0.9)

    def set_state(self, state: OverlayState, message: str = "") -> None:
        if state not in _STATE_COLORS:
            log.warning("Unbekannter Overlay-Zustand: %s", state)
            return
        self._state = state
        self._color = _STATE_COLORS[state]
        self._status_label.setText(message or self._default_message(state))
        self.update()

    def set_status_text(self, text: str) -> None:
        self._status_label.setText(text)

    @staticmethod
    def _default_message(state: OverlayState) -> str:
        return {
            OverlayState.IDLE: "Bereit",
            OverlayState.LISTENING: "Hört zu...",
            OverlayState.THINKING: "Denkt nach...",
            OverlayState.SPEAKING: "Spricht...",
            OverlayState.WARNING: "Warnung",
        }[state]

    def _step_pulse(self) -> None:
        self._pulse = (self._pulse + 0.08) % (2.0)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = self.width() // 2, self.height() // 2 - 20
        radius = 40 + 6 * abs(self._pulse - 1.0)

        gradient = QRadialGradient(cx, cy, radius)
        gradient.setColorAt(0.0, self._color)
        gradient.setColorAt(0.6, QColor(self._color.red(), self._color.green(), self._color.blue(), 80))
        gradient.setColorAt(1.0, QColor(self._color.red(), self._color.green(), self._color.blue(), 0))

        painter.setBrush(gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2))

        # Core orb
        painter.setBrush(self._color)
        painter.drawEllipse(cx - 16, cy - 16, 32, 32)


if __name__ == "__main__":
    app = QApplication([])
    overlay = OverlayWindow()
    overlay.show()
    app.exec()
