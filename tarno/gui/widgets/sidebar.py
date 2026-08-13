"""BuildMC-style navigation sidebar with icon+label items."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SidebarNavItem(QPushButton):
    """Row button with icon and label for the sidebar."""

    def __init__(self, icon_text: str, label_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebarNavItem")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)

        icon = QLabel(icon_text)
        icon.setObjectName("sidebarNavIcon")
        icon.setStyleSheet("background: transparent; font-size: 16px;")
        layout.addWidget(icon)

        label = QLabel(label_text)
        label.setObjectName("sidebarNavLabel")
        label.setStyleSheet("background: transparent; font-size: 13px;")
        layout.addWidget(label)
        layout.addStretch()


class Sidebar(QFrame):
    """240px wide BuildMC-style sidebar with brand header and footer."""

    page_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Brand header
        brand = QFrame()
        brand.setObjectName("sidebarBrand")
        brand.setFixedHeight(64)
        brand_layout = QVBoxLayout(brand)
        brand_layout.setContentsMargins(16, 12, 16, 12)
        brand_layout.setSpacing(0)

        title = QLabel("TARNO")
        title.setObjectName("brandTitle")
        brand_layout.addWidget(title)

        subtitle = QLabel("AI Assistant")
        subtitle.setObjectName("brandSub")
        brand_layout.addWidget(subtitle)

        layout.addWidget(brand)

        # Navigation
        nav_container = QFrame()
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(8, 12, 8, 12)
        nav_layout.setSpacing(4)

        self._buttons: list[SidebarNavItem] = []

        pages = [
            ("\U0001F4CA", "Dashboard"),
            ("\U0001F4AC", "Chat"),
            ("\U0001F3A7", "Voice"),
            ("\U0001F4CB", "Tasks"),
            ("\U0001F50C", "Plugins"),
            ("\U0001F4BE", "Memory"),
            ("\U0001F5A5", "Browser"),
            ("\U0001F5A8", "Models"),
            ("\U0001F6E0", "Settings"),
            ("\U0001F4D6", "Logs"),
        ]

        for i, (icon, label) in enumerate(pages):
            btn = SidebarNavItem(icon, label)
            btn.clicked.connect(lambda checked, idx=i: self._on_click(idx))
            nav_layout.addWidget(btn)
            self._buttons.append(btn)

        nav_layout.addStretch()
        layout.addWidget(nav_container)

        # Footer
        footer = QFrame()
        footer.setObjectName("sidebarFooter")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(16, 12, 16, 12)
        version = QLabel("TARNO v5.0 · Windows")
        version.setObjectName("sidebarFooterText")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer_layout.addWidget(version)
        layout.addWidget(footer)

        self._buttons[0].setChecked(True)

    def select(self, index: int) -> None:
        """Programmatically select a page (keeps sidebar highlight in sync)."""
        self._on_click(index)

    def _on_click(self, index: int) -> None:
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == index)
        self.page_selected.emit(index)
