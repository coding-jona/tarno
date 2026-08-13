"""Settings dialog for the TARNO control UI."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from tarno.core.config import TarnoConfig, UIConfig

log = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Dialog to edit UI and basic settings."""

    def __init__(self, config: TarnoConfig, save_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("TARNO Einstellungen")
        self.resize(500, 350)
        self._config = config
        self._ui_config = config.ui
        self._save_path = save_path

        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Autostart
        self._autostart = QCheckBox("Mit Windows starten")
        self._autostart.setChecked(self._is_autostart_enabled())
        form.addRow(self._autostart)

        # Start minimized
        self._minimized = QCheckBox("Minimiert im Tray starten")
        self._minimized.setChecked(self._ui_config.start_minimized)
        form.addRow(self._minimized)


        layout.addLayout(form)

        note = QLabel("Hinweis: Die meisten Änderungen benötigen einen Neustart von TARNO.")
        note.setStyleSheet("color: #64748b; font-size: 12px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _is_autostart_enabled(self) -> bool:
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run")
            try:
                value, _ = winreg.QueryValueEx(key, "TARNO")
                return bool(value)
            except FileNotFoundError:
                return False
            finally:
                winreg.CloseKey(key)
        except Exception:
            return False

    def _set_autostart(self, enabled: bool) -> None:
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            if enabled:
                import sys
                exe = Path(sys.executable).resolve()
                if exe.name.lower() in ("python.exe", "pythonw.exe"):
                    return
                winreg.SetValueEx(key, "TARNO", 0, winreg.REG_SZ, str(exe))
            else:
                try:
                    winreg.DeleteValue(key, "TARNO")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception:
            log.exception("Autostart konnte nicht gesetzt werden")

    def _save(self) -> None:
        self._ui_config.autostart = self._autostart.isChecked()
        self._ui_config.start_minimized = self._minimized.isChecked()
        self._set_autostart(self._autostart.isChecked())
        self._config.ui = self._ui_config
        try:
            self._save_path.parent.mkdir(parents=True, exist_ok=True)
            self._config.save(self._save_path)
        except Exception:
            log.exception("Einstellungen konnten nicht gespeichert werden")
        self.accept()

    def get_config(self) -> UIConfig:
        return self._ui_config
