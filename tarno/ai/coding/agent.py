"""High-level coding agent used by the engine and gRPC bridge."""

from __future__ import annotations

import logging
import os
from typing import Any, Callable

from tarno.ai.coding.dispatcher import CodingDispatcher
from tarno.ai.coding.exceptions import WorkspaceNotAGitRepoError
from tarno.ai.coding.protocol import CodingOutput
from tarno.core.action_result import ActionResult
from tarno.core.events import CodingOutputEvent, EventBus
from tarno.core.exceptions import PermissionDeniedError
from tarno.core.permission_service import AutonomyMode, PermissionService

log = logging.getLogger(__name__)

GetWorkspace = Callable[[], dict[str, Any] | None]


class CodingAgent:
    """Coordinates workspace validation, backend dispatch and output streaming."""

    def __init__(
        self,
        config,
        event_bus: EventBus | None = None,
        get_workspace: GetWorkspace | None = None,
        permission_service: PermissionService | None = None,
        secrets: Any | None = None,
    ) -> None:
        self.config = config
        self.event_bus = event_bus
        self.get_workspace = get_workspace
        self._permission_service = permission_service
        self.dispatcher = CodingDispatcher(config, secrets)

    def _active_workspace(self) -> dict[str, Any] | None:
        if self.get_workspace is None:
            return None
        return self.get_workspace()

    def _roots(self, workspace: dict[str, Any]) -> list[str]:
        folders = workspace.get("folders", []) or []
        roots = [f.get("path", "") for f in folders if f.get("path", "")]
        if not roots and workspace.get("root_path"):
            roots = [workspace["root_path"]]
        return roots

    def _resolve_paths(
        self, workspace: dict[str, Any], file_paths: list[str]
    ) -> list[str]:
        roots = self._roots(workspace)
        if not roots:
            raise WorkspaceNotAGitRepoError(
                "Kein Workspace-Root für relative Pfade vorhanden."
            )
        resolved: list[str] = []
        for p in file_paths:
            if os.path.isabs(p):
                abs_path = os.path.abspath(p)
            else:
                abs_path = os.path.abspath(os.path.join(roots[0], p))
            ok = any(os.path.commonpath([abs_path, r]) == r for r in roots)
            if not ok:
                raise WorkspaceNotAGitRepoError(
                    f"Pfad außerhalb des Workspace: {p}"
                )
            resolved.append(abs_path)
        return resolved

    def _read_only(self, override: bool | None) -> bool:
        if override is not None:
            return override
        try:
            mode = AutonomyMode(self.config.command_execution.autonomy_mode)
        except ValueError:
            mode = AutonomyMode.BALANCED
        if mode in (AutonomyMode.MANUAL, AutonomyMode.BALANCED):
            return True
        return self.config.coding.read_only_default

    def _publish(self, output: CodingOutput, chat_id: str = "") -> None:
        if self.event_bus is None:
            return
        self.event_bus.publish(
            CodingOutputEvent(
                kind=output.kind,
                text=output.text,
                timestamp_ms=output.timestamp_ms,
                chat_id=chat_id,
                meta=output.meta,
            )
        )

    def execute_task(
        self,
        prompt: str,
        file_paths: list[str] | None = None,
        read_only: bool | None = None,
        chat_id: str = "",
    ) -> ActionResult:
        """Tool handler entry point called by ``TarnoEngine.tools``."""
        workspace = self._active_workspace()
        if not workspace:
            return ActionResult(
                success=False,
                message="Kein aktiver Workspace ausgewählt.",
                error_code="NoWorkspace",
            )
        roots = self._roots(workspace)
        if not roots:
            return ActionResult(
                success=False,
                message="Workspace hat keinen Root-Ordner.",
                error_code="NoWorkspaceRoot",
            )

        try:
            fnames = self._resolve_paths(workspace, file_paths or [])
        except WorkspaceNotAGitRepoError as exc:
            return ActionResult(
                success=False,
                message=str(exc),
                error_code="PathOutsideWorkspace",
            )

        ro = self._read_only(read_only)
        if not ro and self._permission_service is not None:
            try:
                self._permission_service.request_coding_edit(
                    prompt, auto_allow=self.config.coding.auto_allow
                )
            except PermissionDeniedError as exc:
                return ActionResult(
                    success=False,
                    message=str(exc),
                    error_code="PermissionDenied",
                )

        backend = self.dispatcher.get_backend()
        outputs: list[CodingOutput] = []

        def _on_output(output: CodingOutput) -> None:
            outputs.append(output)
            self._publish(output, chat_id=chat_id)

        try:
            for output in backend.run(
                prompt, workspace, fnames, read_only=ro, on_output=_on_output
            ):
                outputs.append(output)
                self._publish(output, chat_id=chat_id)
        except Exception as exc:
            log.exception("Coding-Agent-Fehler")
            return ActionResult(
                success=False,
                message=f"Coding-Task fehlgeschlagen: {exc}",
                error_code="CodingBackendError",
            )

        if outputs and outputs[-1].kind == "summary":
            summary = outputs[-1].text
        elif outputs and outputs[-1].kind == "error":
            summary = outputs[-1].text
        else:
            summary = "Coding-Task abgeschlossen."
        return ActionResult(
            success=True,
            message=summary,
            details={"outputs": len(outputs), "read_only": ro},
        )

    def run(
        self,
        prompt: str,
        workspace: dict[str, Any],
        fnames: list[str],
        read_only: bool,
        chat_id: str = "",
    ) -> list[CodingOutput]:
        """Direct gRPC/streaming entry point that bypasses the tool registry."""
        backend = self.dispatcher.get_backend()
        outputs: list[CodingOutput] = []

        def _on_output(output: CodingOutput) -> None:
            outputs.append(output)
            self._publish(output, chat_id=chat_id)

        for output in backend.run(
            prompt, workspace, fnames, read_only=read_only, on_output=_on_output
        ):
            outputs.append(output)
            self._publish(output, chat_id=chat_id)
        return outputs
