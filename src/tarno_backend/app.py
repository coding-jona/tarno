"""GUI application entry point."""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from tarno_backend.core.config import TarnoConfig
from tarno_backend.core.service_mediator import ServiceMediator
from tarno_backend.desktop.system_info import get_cpu_ram_stats, get_gpu_name
from tarno_backend.gui.log_bridge import QtLogHandler
from tarno_backend.gui.main_window import MainWindow
from tarno_backend.gui.theme import get_stylesheet


def run_gui(config: TarnoConfig) -> None:
    """Create and run the TARNO GUI application."""
    app = QApplication(sys.argv)
    app.setApplicationName("TARNO AI Assistant")
    app.setApplicationVersion("5.0")
    app.setStyleSheet(get_stylesheet())

    mediator = ServiceMediator(config)

    window = MainWindow()

    # Wire GUI → Mediator
    window.chat_panel.text_submitted.connect(mediator.send_text)
    window.chat_panel.voice_toggled.connect(mediator.toggle_voice)

    # Wire Mediator → GUI
    mediator.message_received.connect(window.chat_panel.add_message)
    mediator.status_changed.connect(window.status_bar.set_state)
    mediator.status_changed.connect(_update_thinking(window))
    mediator.mic_state_changed.connect(
        lambda active: window.chat_panel.set_mic_state("listening" if active else "off")
    )
    mediator.error_occurred.connect(
        lambda msg: window.chat_panel.add_message("assistant", f"Fehler: {msg}")
    )

    # Set initial state
    window.status_bar.set_provider(mediator.provider_name)
    window.status_bar.set_state("Bereit")
    window.dashboard.set_provider(mediator.provider_name)
    window.dashboard.set_status("Bereit")

    # Mirror status changes to dashboard
    mediator.status_changed.connect(window.dashboard.set_status)

    # Dashboard quick actions
    def _on_voice_requested() -> None:
        window.navigate_to(1)
        mediator.toggle_voice(True)

    window.dashboard.chat_requested.connect(lambda: window.navigate_to(1))
    window.dashboard.voice_requested.connect(_on_voice_requested)
    window.dashboard.plugins_requested.connect(lambda: window.navigate_to(4))

    # Live system stats on the dashboard
    def _refresh_stats() -> None:
        cpu, ram = get_cpu_ram_stats()
        window.dashboard.set_cpu_ram(cpu, ram)

    _refresh_stats()
    stats_timer = QTimer(window)
    stats_timer.timeout.connect(_refresh_stats)
    stats_timer.start(2000)
    QTimer.singleShot(200, lambda: window.dashboard.set_gpu(get_gpu_name()))

    # Live log feed on the dashboard
    log_handler = QtLogHandler()
    log_handler.log_emitted.connect(window.dashboard.add_log)
    logging.getLogger().addHandler(log_handler)

    window.show()

    # Cleanup on exit
    app.aboutToQuit.connect(mediator.shutdown)

    sys.exit(app.exec())


def _update_thinking(window: MainWindow):
    """Return a slot that toggles the thinking indicator."""
    def handler(state: str) -> None:
        window.chat_panel.set_thinking(state == "Denkt nach...")
    return handler
