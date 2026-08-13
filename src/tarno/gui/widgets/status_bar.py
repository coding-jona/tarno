"""Bottom status bar showing provider and state."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from tarno.gui.theme import COLORS


class StatusBar(QFrame):
    """Thin bar at the bottom: provider name + current state."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusBar")
        self.setFixedHeight(28)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)

        self._dot = QLabel("●")
        self._dot.setObjectName("statusDot")
        self._dot.setFixedWidth(14)
        layout.addWidget(self._dot)

        self._provider_label = QLabel("Provider: —")
        layout.addWidget(self._provider_label)

        layout.addStretch()

        self._state_label = QLabel("Bereit")
        layout.addWidget(self._state_label)

    def set_provider(self, name: str) -> None:
        self._provider_label.setText(f"Provider: {name}")

    def set_state(self, state: str) -> None:
        self._state_label.setText(state)
        color_map = {
            "Bereit": COLORS["success"],
            "Denkt nach...": COLORS["warning"],
            "Spricht...": COLORS["brand_500"],
            "Hört zu...": COLORS["error"],
        }
        color = color_map.get(state, COLORS["text_secondary"])
        self._dot.setStyleSheet(f"color: {color};")
