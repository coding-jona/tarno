"""Generic placeholder page — BuildMC AI Desktop style."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from tarno_backend.gui.theme import COLORS


class PlaceholderPage(QWidget):
    """A BuildMC-style placeholder page with a centered message inside a card."""

    def __init__(self, title: str, subtitle: str, icon: str, parent: QWidget | None = None) -> None:
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

        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        title_label.setStyleSheet("background: transparent;")
        header_layout.addWidget(title_label)

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("pageSubtitle")
        subtitle_label.setStyleSheet("background: transparent;")
        header_layout.addWidget(subtitle_label)
        layout.addWidget(header)

        # Centered card
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)

        icon_label = QLabel(icon)
        icon_label.setStyleSheet(
            f"background: transparent; font-size: 48px; color: {COLORS['brand_400']};"
        )
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(icon_label)

        msg = QLabel(f"{title} — kommt in Phase 2")
        msg.setStyleSheet(
            f"background: transparent; color: {COLORS['text_secondary']}; font-size: 14px;"
        )
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(msg)

        layout.addWidget(card)
        layout.addStretch()
