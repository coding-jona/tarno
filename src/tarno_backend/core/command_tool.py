"""Tool handler that exposes the command execution engine to the LLM."""

from __future__ import annotations

import logging
from typing import Any

from tarno_backend.ai.context.output_compressor import compress_tool_output_detailed
from tarno_backend.core.action_logger import get_action_logger
from tarno_backend.core.action_result import ActionResult
from tarno_backend.core.command_engine import CommandEngine, PreparedCommand, RiskLevel
from tarno_backend.core.config import TarnoConfig
from tarno_backend.core.exceptions import CommandBlockedError, PermissionDeniedError
from tarno_backend.core.executor import ShellExecutor
from tarno_backend.core.permission_service import AutonomyMode, PermissionService
from tarno_backend.core.workspace import get_workspace_roots
from tarno_backend.ui.confirmation_dialog import create_default_confirmation

log = logging.getLogger(__name__)


class CommandTool:
    """Encapsulates the full command execution flow as a tool handler."""

    def __init__(
        self,
        config: TarnoConfig | None = None,
        permission_service: PermissionService | None = None,
    ) -> None:
        self._config = config or TarnoConfig.load()
        timeout = self._config.command_execution.timeout
        self._engine = CommandEngine(default_timeout=timeout)
        self._executor = ShellExecutor(default_timeout=timeout)
        # Qt dialog is used when a QApplication exists (PySide6 GUI mode);
        # otherwise the console fallback is used (voice/headless mode).
        if permission_service is not None:
            self._permissions = permission_service
        else:
            try:
                default_mode = AutonomyMode(self._config.command_execution.autonomy_mode)
            except ValueError:
                log.warning(
                    "Unbekannter autonomy_mode '%s' in Konfiguration, verwende 'balanced'",
                    self._config.command_execution.autonomy_mode,
                )
                default_mode = AutonomyMode.BALANCED
            self._permissions = PermissionService(
                dialog_factory=create_default_confirmation(prefer_qt=True),
                mode=default_mode,
            )
        self._logger = get_action_logger(self._config.command_execution)

    def set_autonomy_mode(self, mode: AutonomyMode) -> None:
        """Change the live autonomy mode (see AutonomyMode for semantics)."""
        self._permissions.set_mode(mode)

    @property
    def autonomy_mode(self) -> AutonomyMode:
        return self._permissions.mode

    def configure_remote_permissions(self, dialog_factory, safety_phrase_confirm=None) -> None:
        """Replace the Qt/console confirmation with a remote (e.g. gRPC/WinUI) one.

        Called by the gRPC bridge for the real (non-mock) engine: the backend
        process has no Qt event loop and no attached console, so the default
        dialog_factory chain would hang on input() instead of ever resolving.
        """
        self._permissions.set_dialog_factory(dialog_factory, safety_phrase_confirm)

    def close_window_gated(self, title_substring: str, user_query: str = "") -> ActionResult:
        """Close a window by title substring, gated through the same
        risk/permission pipeline as shell commands (respects the current
        AutonomyMode). Used by ProactiveEngine's anti-distraction escalation
        (Block 3, Phase 28) so an autonomous window-close still honors
        Manual/Balanced/Plan/Ultimate rather than bypassing the risk router
        the way a direct ToolRegistry call would.
        """
        from tarno_backend.desktop.window_manager import close_window

        risk_level = self._engine.assess_risk("close_window", title_substring, "close_window")
        if risk_level == RiskLevel.BLOCKED:
            return ActionResult(
                success=False,
                message="Fenster-Schließen durch Sicherheitsrichtlinie blockiert.",
                error_code="Blocked",
            )

        prepared = PreparedCommand(
            action="close_window",
            shell="",
            command=title_substring,
            params={},
            risk_level=risk_level,
            intent="close_window",
            user_query=user_query,
            timeout=self._config.command_execution.timeout,
            explanation=f"Fenster '{title_substring}' schließen",
        )

        try:
            self._permissions.request_approval(prepared)
        except PermissionDeniedError as exc:
            log.info("Fenster-Schließen abgelehnt: %s", exc)
            return ActionResult(success=False, message=f"Abgelehnt: {exc}", error_code="PermissionDenied")

        return close_window(title_substring)

    def __call__(self, workspace: dict[str, Any] | None = None, **tool_input: Any) -> str:
        """Synchronous entry point used by ToolRegistry."""
        if not self._config.command_execution.enabled:
            return "Command Execution ist in der Konfiguration deaktiviert."

        user_query = tool_input.get("user_query", "")
        request = {
            "action": tool_input.get("action", "execute_command"),
            "shell": tool_input.get("shell", "powershell"),
            "command": tool_input.get("command", ""),
            "params": tool_input.get("params") or {},
            "intent": tool_input.get("intent", "execute_command"),
            "explanation": tool_input.get("explanation", ""),
        }

        try:
            prepared = self._engine.prepare(request, user_query=user_query)
            self._permissions.request_approval(prepared)
        except CommandBlockedError as exc:
            log.warning("Command blockiert: %s", exc)
            return f"Abgelehnt: {exc}"
        except PermissionDeniedError as exc:
            log.info("Berechtigung verweigert: %s", exc)
            return f"Abgelehnt: {exc}"

        # PLAN mode never lets a real command run - CommandTool forces a dry run
        # regardless of config, and PermissionService auto-grants every risk
        # level in this mode (see PermissionService._auto_grants) since nothing
        # destructive actually happens here.
        force_dry_run = self._permissions.mode == AutonomyMode.PLAN
        roots = get_workspace_roots(workspace)
        cwd = str(roots[0]) if roots else None
        try:
            result = self._executor.execute_sync(
                prepared,
                dry_run=force_dry_run or self._config.command_execution.dry_run_default,
                cwd=cwd,
            )
        except Exception as exc:
            log.exception("Ausführungsfehler")
            return f"Fehler bei der Ausführung: {exc}"

        self._logger.log(
            user_query=prepared.user_query,
            intent=prepared.intent,
            shell=prepared.shell,
            command=prepared.command,
            risk_level=prepared.risk_level.value,
            result=result,
        )

        # Kontext-Effizienz Phase 2: der groesste unkomprimierte Output-
        # Erzeuger im ganzen Tool-Registry (Shell-/Build-Logs) - hier direkt
        # angewendet statt nur ueber engine.py's chat_mode-gated Hook, weil
        # CommandTool auch von ServiceMediator (Qt GUI) und agent_service.py
        # (OVOS) ohne diesen Hook genutzt wird. Idempotent/no-op-sicher bei
        # bereits kurzem Text, daher harmlos falls engine.py denselben Text
        # zusaetzlich komprimiert.
        raw = str(result)
        compressed, info = compress_tool_output_detailed(raw, tool_name="execute_command")
        if info.strategy_notes:
            log.debug(
                "[CtxEff] execute_command komprimiert: %d -> %d Zeichen (%s)",
                info.original_chars, info.compressed_chars, info.strategy_notes,
            )
        return compressed
