"""Main application window — BuildMC AI Layout.tsx clone."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from tarno_backend.gui.pages.dashboard import DashboardPage
from tarno_backend.gui.pages.placeholder import PlaceholderPage
from tarno_backend.gui.widgets.chat_panel import ChatPanel
from tarno_backend.gui.widgets.sidebar import Sidebar
from tarno_backend.gui.widgets.status_bar import StatusBar


class MainWindow(QMainWindow):
    """TARNO main window: sidebar + content stack + status bar."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TARNO AI Assistant")
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)

        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Main area: sidebar + content
        main_area = QWidget()
        main_layout = QHBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar()
        main_layout.addWidget(self.sidebar)

        # Content stack
        self._stack = QStackedWidget()
        self._stack.setObjectName("contentStack")
        main_layout.addWidget(self._stack)

        # Pages matching the sidebar order (Dashboard first, Chat second)
        self.dashboard = DashboardPage()
        self._stack.addWidget(self.dashboard)

        self.chat_panel = ChatPanel()
        self._stack.addWidget(self.chat_panel)

        placeholder_pages = [
            ("Voice", "Sprachsteuerung und Wake-Word-Status.", "🎙"),
            ("Tasks", "Aufgaben, Automatisierung und Zeitpläne.", "📝"),
            ("Plugins", "Tools, Browser-Integration und Erweiterungen.", "🔌"),
            ("Memory", "Gespeicherte Konversationen und Wissensbasis.", "🧠"),
            ("Browser", "Web-Recherche und Browser-Steuerung.", "🌐"),
            ("Models", "LLM-Provider und Modell-Konfiguration.", "🤖"),
            ("Settings", "App-Einstellungen, Theme und API-Keys.", "⚙️"),
            ("Logs", "System- und Anwendungsprotokolle.", "📋"),
        ]

        for title, subtitle, icon in placeholder_pages:
            self._stack.addWidget(PlaceholderPage(title, subtitle, icon))

        self.sidebar.page_selected.connect(self._stack.setCurrentIndex)

        root_layout.addWidget(main_area)

        # Status bar
        self.status_bar = StatusBar()
        root_layout.addWidget(self.status_bar)

    def navigate_to(self, index: int) -> None:
        """Switch pages and keep the sidebar selection in sync."""
        self.sidebar.select(index)
