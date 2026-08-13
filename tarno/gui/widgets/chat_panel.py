"""Chat panel — BuildMC AI Chat.tsx clone for TARNO."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from tarno.gui.theme import COLORS
from tarno.gui.widgets.mic_indicator import MicIndicator


class _MessageRow(QWidget):
    """A single chat row with sender name and bubble."""

    def __init__(self, text: str, role: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        name = QLabel("You" if role == "user" else "TARNO")
        name.setObjectName("bubbleName")
        name.setStyleSheet("background: transparent;")
        if role == "user":
            name.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(name)

        row = QHBoxLayout()
        row.setSpacing(0)

        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bubble_id = "bubbleUser" if role == "user" else "bubbleAssistant"
        bubble.setObjectName(bubble_id)
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
        label = QLabel("Thinking...")
        label.setObjectName("bubbleAssistant")
        layout.addWidget(label)
        layout.addStretch()
        self.hide()


class ChatPanel(QWidget):
    """BuildMC AI style chat view."""

    text_submitted = Signal(str)
    voice_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Page header
        header = QFrame()
        header.setObjectName("pageHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(24, 24, 24, 16)
        header_layout.setSpacing(2)

        title = QLabel("Chat")
        title.setObjectName("pageTitle")
        title.setStyleSheet("background: transparent;")
        header_layout.addWidget(title)

        subtitle = QLabel("Start a conversation with TARNO.")
        subtitle.setObjectName("pageSubtitle")
        subtitle.setStyleSheet("background: transparent;")
        header_layout.addWidget(subtitle)
        layout.addWidget(header)

        # Chat card with scroll area
        chat_card = QFrame()
        chat_card.setObjectName("chatCard")
        card_layout = QVBoxLayout(chat_card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("chatScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._container = QWidget()
        self._container.setObjectName("chatContainer")
        self._messages_layout = QVBoxLayout(self._container)
        self._messages_layout.setContentsMargins(0, 0, 0, 0)
        self._messages_layout.setSpacing(12)
        self._messages_layout.addStretch()

        self._empty = QLabel("Start a conversation with TARNO.")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(
            f"background: transparent; color: {COLORS['text_muted']}; font-size: 13px; padding: 40px;"
        )
        self._messages_layout.insertWidget(0, self._empty)

        self._thinking = _ThinkingRow()
        self._messages_layout.addWidget(self._thinking)

        self._scroll.setWidget(self._container)
        card_layout.addWidget(self._scroll)
        layout.addWidget(chat_card, 1)

        # Input area
        input_area = QFrame()
        input_area.setObjectName("inputArea")
        input_layout = QHBoxLayout(input_area)
        input_layout.setContentsMargins(16, 12, 16, 12)
        input_layout.setSpacing(12)

        self._mic = MicIndicator()
        self._mic.toggled_voice.connect(self.voice_toggled)
        input_layout.addWidget(self._mic)

        self._input = QLineEdit()
        self._input.setObjectName("chatInput")
        self._input.setPlaceholderText("Ask something...")
        self._input.returnPressed.connect(self._on_submit)
        input_layout.addWidget(self._input, 1)

        self._send_btn = QPushButton("Send")
        self._send_btn.setObjectName("sendButton")
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

    def set_mic_state(self, state: str) -> None:
        self._mic.set_state(state)

    def _on_submit(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self.text_submitted.emit(text)

    def _scroll_to_bottom(self) -> None:
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())
