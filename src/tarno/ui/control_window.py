"""Main control window for the TARNO UI."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from tarno.ui.widgets.chat_area import ChatArea
from tarno.ui.widgets.log_view import LogView
from tarno.ui.widgets.status_bar import StatusBar


class ControlWindow(QMainWindow):
    """Primary window for controlling TARNO."""

    start_requested = Signal()
    stop_requested = Signal()
    mute_requested = Signal(bool)
    text_submitted = Signal(str)
    settings_requested = Signal()
    task_approved = Signal(str)
    task_rejected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("TARNO Control")
        self.resize(900, 600)
        self.setMinimumSize(700, 450)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet("background-color: #111114; border-bottom: 1px solid #27272a;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(16, 12, 16, 12)
        toolbar_layout.setSpacing(12)

        self._start_btn = QPushButton("Start")
        self._start_btn.setObjectName("btnPrimary")
        self._start_btn.clicked.connect(self.start_requested.emit)
        toolbar_layout.addWidget(self._start_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("btnDanger")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        toolbar_layout.addWidget(self._stop_btn)

        self._settings_btn = QPushButton("Einstellungen")
        self._settings_btn.setObjectName("btnSecondary")
        self._settings_btn.clicked.connect(self.settings_requested.emit)
        toolbar_layout.addWidget(self._settings_btn)

        toolbar_layout.addStretch()

        # Splitter: chat + log
        self._splitter = QSplitter()
        self._splitter.setStyleSheet("QSplitter::handle { background: #27272a; }")

        self._chat = ChatArea()
        self._chat.text_submitted.connect(self.text_submitted.emit)
        self._chat.voice_toggled.connect(self.mute_requested.emit)

        self._log = LogView()

        self._splitter.addWidget(self._chat)
        self._splitter.addWidget(self._log)
        self._splitter.setSizes([500, 200])

        layout.addWidget(toolbar)
        layout.addWidget(self._splitter, 1)

        # Status bar
        self._status = StatusBar()
        layout.addWidget(self._status)

    def append_log(self, text: str) -> None:
        self._log.append_log(text)

    def add_message(self, role: str, text: str) -> None:
        self._chat.add_message(role, text)

    def set_status(self, state: str) -> None:
        self._status.set_state(state)

    def set_engine_running(self, running: bool) -> None:
        self._start_btn.setEnabled(not running)
        self._stop_btn.setEnabled(running)

    def set_thinking(self, active: bool) -> None:
        self._chat.set_thinking(active)

    def set_mic_active(self, active: bool) -> None:
        self._chat.set_mic_state(active)

    def request_task_decision(self, task_id: str, description: str) -> None:
        """Show a modal dialog asking the user to approve or reject a task."""
        box = QMessageBox(self)
        box.setWindowTitle("TARNO — Genehmigung erforderlich")
        box.setText(f"Soll die folgende Aufgabe ausgeführt werden?\n\n{description}")
        approve_btn = box.addButton("Genehmigen", QMessageBox.ButtonRole.AcceptRole)
        reject_btn = box.addButton("Ablehnen", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() == approve_btn:
            self.task_approved.emit(task_id)
        elif box.clickedButton() == reject_btn:
            self.task_rejected.emit(task_id)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Minimize to tray instead of closing the application."""
        event.ignore()
        self.hide()
