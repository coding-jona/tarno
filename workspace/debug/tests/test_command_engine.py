"""Tests for the command execution engine and shell executor."""

from __future__ import annotations

import sys
import unittest
from datetime import timedelta

from tarno_backend.core.action_result import ActionResult
from tarno_backend.core.command_engine import CommandEngine, RiskLevel
from tarno_backend.core.exceptions import CommandBlockedError, PermissionDeniedError
from tarno_backend.core.executor import ShellExecutor
from tarno_backend.core.permission_service import AutonomyMode, PermissionService


class CommandEngineTests(unittest.TestCase):
    """Unit tests for CommandEngine risk assessment and blocking."""

    def setUp(self) -> None:
        self.engine = CommandEngine(default_timeout=30.0)

    def test_network_diagnostic_is_low_risk(self):
        prepared = self.engine.prepare({
            "intent": "network_check",
            "shell": "powershell",
            "command": "Test-Connection 8.8.8.8 -Count 1",
        })
        self.assertEqual(prepared.risk_level, RiskLevel.LOW)

    def test_package_manager_is_medium_risk(self):
        prepared = self.engine.prepare({
            "intent": "software_install",
            "shell": "powershell",
            "command": "winget install Notepad++.Notepad++",
        })
        self.assertEqual(prepared.risk_level, RiskLevel.MEDIUM)

    def test_shutdown_is_high_risk(self):
        prepared = self.engine.prepare({
            "intent": "shutdown",
            "shell": "powershell",
            "command": "Stop-Computer -Force",
        })
        self.assertEqual(prepared.risk_level, RiskLevel.HIGH)

    def test_invoke_expression_is_blocked(self):
        with self.assertRaises(CommandBlockedError):
            self.engine.prepare({
                "intent": "run_code",
                "shell": "powershell",
                "command": "Invoke-Expression 'Get-Process'",
            })

    def test_empty_command_is_blocked(self):
        with self.assertRaises(CommandBlockedError):
            self.engine.prepare({
                "intent": "empty",
                "shell": "powershell",
                "command": "   ",
            })

    def test_build_result_reports_success_truthfully(self):
        prepared = self.engine.prepare({
            "intent": "list_files",
            "shell": "bash",
            "command": "ls",
        })
        result = self.engine.build_result(
            prepared,
            returncode=0,
            stdout="file.txt\n",
            stderr="",
        )
        self.assertIsInstance(result, ActionResult)
        self.assertTrue(result.success)
        self.assertIn("erfolgreich", result.message)

    def test_build_result_reports_failure_truthfully(self):
        prepared = self.engine.prepare({
            "intent": "list_files",
            "shell": "bash",
            "command": "ls /nonexistent",
        })
        result = self.engine.build_result(
            prepared,
            returncode=2,
            stdout="",
            stderr="No such file or directory",
        )
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error_code)


class ShellExecutorTests(unittest.TestCase):
    """Tests for ShellExecutor with safe commands."""

    def setUp(self) -> None:
        self.executor = ShellExecutor(default_timeout=10.0)
        self.engine = CommandEngine(default_timeout=10.0)

    def _prepare(self, intent: str, command: str, shell: str = "cmd"):
        return self.engine.prepare({
            "intent": intent,
            "shell": shell,
            "command": command,
        })

    def test_echo_command_succeeds(self):
        if sys.platform != "win32":
            self.skipTest("Windows-only command")
        prepared = self._prepare("echo_test", "echo hello", shell="cmd")
        result = self.executor.execute_sync(prepared)
        self.assertTrue(result.success)
        self.assertIn("hello", (result.message or "").lower())

    def test_dry_run_does_not_execute(self):
        prepared = self._prepare("danger", "format C:", shell="cmd")
        result = self.executor.execute_sync(prepared, dry_run=True)
        self.assertTrue(result.success)
        self.assertIn("DRY-RUN", result.message)


class PermissionServiceTests(unittest.TestCase):
    """Tests for the permission approval flow."""

    def test_low_risk_auto_approved(self):
        service = PermissionService()
        engine = CommandEngine()
        prepared = engine.prepare({
            "intent": "ping",
            "shell": "cmd",
            "command": "ping 127.0.0.1 -n 1",
        })
        self.assertTrue(service.request_approval(prepared))

    def test_medium_risk_approved_by_fake_dialog(self):
        # MANUAL mode, otherwise AutonomyMode.BALANCED would auto-grant MEDIUM
        # without ever calling the fake dialog, and this test would pass for
        # the wrong reason.
        service = PermissionService(
            dialog_factory=lambda permission, target, risk, duration: (True, False),
            mode=AutonomyMode.MANUAL,
        )
        engine = CommandEngine()
        prepared = engine.prepare({
            "intent": "software_install",
            "shell": "powershell",
            "command": "winget install Example.App",
        })
        self.assertTrue(service.request_approval(prepared))

    def test_medium_risk_denied_by_fake_dialog(self):
        # MANUAL mode explicitly, since AutonomyMode.BALANCED (the default
        # since Block 2) auto-grants MEDIUM risk without ever consulting the
        # dialog - this test is specifically about the "always ask" dialog
        # flow, which only applies under MANUAL.
        service = PermissionService(
            dialog_factory=lambda permission, target, risk, duration: (False, False),
            mode=AutonomyMode.MANUAL,
        )
        engine = CommandEngine()
        prepared = engine.prepare({
            "intent": "software_install",
            "shell": "powershell",
            "command": "winget install Example.App",
        })
        with self.assertRaises(PermissionDeniedError):
            service.request_approval(prepared)


class ConfirmationDialogSelectionTests(unittest.TestCase):
    """Tests that the right confirmation dialog is selected per runtime mode."""

    def test_headless_mode_uses_console_confirmation(self):
        """Without a QApplication the console fallback must be selected."""
        from tarno_backend.ui.confirmation_dialog import create_default_confirmation

        dialog = create_default_confirmation(prefer_qt=True)
        self.assertEqual(dialog.__name__, "show_console_confirmation")

    @unittest.skipUnless(
        __import__("importlib").util.find_spec("PySide6") is not None,
        "PySide6 nicht installiert (optionale --legacy-ui Abhängigkeit, siehe TD-006/TD-017)",
    )
    def test_gui_mode_uses_qt_presenter(self):
        """With a QApplication the Qt presenter must be selected."""
        from unittest.mock import patch

        from tarno_backend.ui import confirmation_dialog

        fake_app = object()
        with patch.object(
            confirmation_dialog.QApplication, "instance", return_value=fake_app
        ):
            with patch.object(
                confirmation_dialog,
                "QtConfirmationPresenter",
                autospec=True,
            ) as mock_presenter:
                from tarno_backend.ui.confirmation_dialog import create_default_confirmation

                dialog = create_default_confirmation(prefer_qt=True)
                mock_presenter.assert_called_once()
                self.assertTrue(callable(dialog))


if __name__ == "__main__":
    unittest.main()
