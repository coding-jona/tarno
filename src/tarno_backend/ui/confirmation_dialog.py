"""Confirmation dialogs for risky TARNO actions.

Provides both a native PySide6 dialog and a text fallback for headless mode.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Callable, Tuple

from tarno_backend.core.command_engine import RiskLevel
from tarno_backend.core.permission_service import PermissionType

log = logging.getLogger(__name__)

ConfirmationResult = Tuple[bool, bool]  # (approved, persistent)


def show_console_confirmation(
    permission: PermissionType,
    target: str,
    risk: RiskLevel,
    duration: timedelta | None,
) -> ConfirmationResult:
    """Text-based confirmation dialog for console/headless mode."""
    print("\n" + "=" * 60)
    print("TARNO – Aktion bestätigen")
    print("=" * 60)
    print(f"Aktion: {permission.value}")
    print(f"Ziel:   {target}")
    print(f"Risiko: {risk.value.upper()}")
    if duration:
        print(f"Dauer:  {duration}")
    print("=" * 60)

    try:
        answer = input("Ausführen? [einmal (j) / dauerhaft (d) / abbrechen (N)]: ")
    except (EOFError, KeyboardInterrupt):
        return False, False

    text = answer.strip().lower()
    if text in ("j", "ja", "y", "yes"):
        return True, False
    if text in ("d", "dauerhaft", "p", "permanent"):
        return True, True
    return False, False


try:
    from PySide6.QtCore import QObject, Qt, QMetaObject, Q_ARG, Slot
    from PySide6.QtWidgets import (
        QInputDialog,
        QMessageBox,
        QWidget,
        QApplication,
    )

    _HAS_QT = True
except Exception:  # pragma: no cover
    _HAS_QT = False


if _HAS_QT:
    class QtConfirmationPresenter(QObject):
        """Opens a Qt confirmation dialog in the GUI thread.

        The presenter is created in the main thread. Calls from worker threads
        are marshalled back to the main thread via BlockingQueuedConnection so
        the dialog is always shown on the correct thread while the caller
        blocks until the user answers.
        """

        def __init__(self, parent: "QWidget | None" = None) -> None:
            super().__init__(parent)
            self._parent = parent
            self._result: ConfirmationResult = (False, False)

        @Slot(object, str, object, object)
        def _show_sync(
            self,
            permission: PermissionType,
            target: str,
            risk: RiskLevel,
            duration: timedelta | None,
        ) -> None:
            self._result = _run_qt_confirmation(
                permission, target, risk, duration, self._parent
            )

        def show_sync(
            self,
            permission: PermissionType,
            target: str,
            risk: RiskLevel,
            duration: timedelta | None,
        ) -> ConfirmationResult:
            app = QApplication.instance()
            if app is None or self.thread() == app.thread():
                self._show_sync(permission, target, risk, duration)
                return self._result
            QMetaObject.invokeMethod(
                self,
                "_show_sync",
                Qt.ConnectionType.BlockingQueuedConnection,
                Q_ARG(object, permission),
                Q_ARG(str, target),
                Q_ARG(object, risk),
                Q_ARG(object, duration),
            )
            return self._result


def _run_qt_confirmation(
    permission: PermissionType,
    target: str,
    risk: RiskLevel,
    duration: timedelta | None,
    parent: "QWidget | None" = None,
) -> ConfirmationResult:
    """Native Qt confirmation dialog.

    For high-risk actions the user must type a safety phrase before the
    'Ausführen' button becomes available.
    """
    if not _HAS_QT:
        log.warning("PySide6 nicht verfügbar, verwende Konsolen-Bestätigung")
        return show_console_confirmation(permission, target, risk, duration)

    msg = QMessageBox(parent)
    msg.setWindowTitle("TARNO – Aktion bestätigen")
    msg.setText(f"Möchten Sie diese Aktion ausführen?\n\n{target}")

    details = [
        f"Aktion: {permission.value}",
        f"Risiko: {risk.value.upper()}",
    ]
    if duration:
        details.append(f"Dauer: {duration}")
    msg.setInformativeText("\n".join(details))

    abort_button = msg.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
    once_button = msg.addButton("Einmal erlauben", QMessageBox.ButtonRole.AcceptRole)
    persistent_button = msg.addButton("Dauerhaft erlauben", QMessageBox.ButtonRole.AcceptRole)

    if risk == RiskLevel.HIGH:
        # High-risk: disable execute buttons until the safety phrase is typed.
        once_button.setEnabled(False)
        persistent_button.setEnabled(False)
        phrase = "Ja, ausführen"
        text, ok = QInputDialog.getText(
            parent,
            "Sicherheitsabfrage",
            f"Geben Sie '{phrase}' ein, um fortzufahren:",
        )
        if not ok or text.strip() != phrase:
            msg.setDefaultButton(abort_button)

    msg.exec()
    clicked = msg.clickedButton()
    if clicked == abort_button:
        return False, False
    if clicked == persistent_button:
        return True, True
    return True, False


def show_qt_confirmation(
    permission: PermissionType,
    target: str,
    risk: RiskLevel,
    duration: timedelta | None,
    parent: "QWidget | None" = None,
) -> ConfirmationResult:
    """Legacy wrapper kept for callers that already run in the GUI thread."""
    return _run_qt_confirmation(permission, target, risk, duration, parent)


def create_default_confirmation(
    prefer_qt: bool = True,
    parent: "QWidget | None" = None,
) -> Callable[..., ConfirmationResult]:
    """Return the best available confirmation function."""
    if prefer_qt and _HAS_QT and QApplication.instance() is not None:
        presenter = QtConfirmationPresenter(parent)
        return lambda permission, target, risk, duration: presenter.show_sync(
            permission, target, risk, duration
        )
    return show_console_confirmation
