"""Chat area widget for the control window."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from tarno.ui.widgets.mic_button import MicButton


class _MessageRow(QWidget):
    """A single chat row with sender name and bubble."""

    def __init__(self, text: str, role: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        name = QLabel("Du" if role == "user" else "TARNO")
        name.setStyleSheet("background: transparent; font-size: 11px; color: #64748b;")
        if role == "user":
            name.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(name)

        row = QHBoxLayout()
        row.setSpacing(0)

        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bubble.setStyleSheet(
            "background-color: #14b8a6; border-radius: 8px; padding: 10px 14px; color: #000000; font-size: 13px;"
            if role == "user"
            else "background-color: #1c1c21; border-radius: 8px; padding: 10px 14px; color: #f1f5f9; font-size: 13px;"
        )
        if role == "user":
            row.addStretch()
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch()
        layout.addLayout(row)


class _ThinkingRow(QWidget):
    """Thinking indicator row."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel("TARNO denkt nach...")
        label.setStyleSheet("background-color: #1c1c21; border-radius: 8px; padding: 10px 14px; color: #94a3b8; font-size: 13px;")
        layout.addWidget(label)
        layout.addStretch()
        self.hide()


class ChatArea(QWidget):
    """Chat view with input and mic toggle."""

    text_submitted = Signal(str)
    voice_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setStyleSheet("border: none; background-color: transparent;")

        self._container = QWidget()
        self._container.setStyleSheet("background-color: transparent;")
        self._messages_layout = QVBoxLayout(self._container)
        self._messages_layout.setContentsMargins(0, 0, 0, 0)
        self._messages_layout.setSpacing(12)
        self._messages_layout.addStretch()

        self._empty = QLabel("Starte eine Unterhaltung mit TARNO.")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet("color: #64748b; font-size: 13px; padding: 40px; background: transparent;")
        self._messages_layout.insertWidget(0, self._empty)

        self._thinking = _ThinkingRow()
        self._messages_layout.addWidget(self._thinking)

        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll, 1)

        # Input area
        input_area = QWidget()
        input_layout = QHBoxLayout(input_area)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(12)

        self._mic = MicButton()
        self._mic.toggled.connect(self.voice_toggled)
        input_layout.addWidget(self._mic)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Gib eine Nachricht ein...")
        self._input.setObjectName("input")
        self._input.returnPressed.connect(self._on_submit)
        input_layout.addWidget(self._input, 1)

        self._send_btn = QPushButton("Senden")
        self._send_btn.setObjectName("btnPrimary")
        self._send_btn.setDefault(True)
        self._send_btn.clicked.connect(self._on_submit)
        input_layout.addWidget(self._send_btn)

        layout.addWidget(input_area)

    def add_message(self, role: str, text: str) -> None:
        self._empty.hide()
        insert_pos = self._messages_layout.count() - 2
        self._messages_layout.insertWidget(insert_pos, _MessageRow(text, role))
        self._scroll_to_bottom()

    def set_thinking(self, active: bool) -> None:
        self._thinking.setVisible(active)
        if active:
            self._scroll_to_bottom()

    def set_mic_state(self, active: bool) -> None:
        self._mic.set_state(active)

    def _on_submit(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self.add_message("user", text)
        self.text_submitted.emit(text)

    def _scroll_to_bottom(self) -> None:
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())
