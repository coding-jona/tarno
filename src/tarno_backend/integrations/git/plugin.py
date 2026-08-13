"""TARNO plugin for Git developer tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tarno_backend.ai.tool_registry import ToolDefinition
from tarno_backend.core.action_result import ActionResult
from tarno_backend.integrations.git.client import GitClient
from tarno_backend.plugins.base import BasePlugin


class GitPlugin(BasePlugin):
    """Provides read-only Git status tools for developer workflows."""

    name = "git_tools"
    version = "1.0.0"
    dependencies: list[str] = []

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="git_status",
                description="Zeigt den Git-Status eines Repositorys an.",
                input_schema={
                    "type": "object",
                    "properties": {"repo_path": {"type": "string", "default": "."}},
                },
                handler=self._status,
            ),
        ]

    def _status(self, repo_path: str = ".") -> ActionResult:
        client = GitClient(Path(repo_path).expanduser())
        if not client.is_repo():
            return self.failure(f"{repo_path} ist kein Git-Repository", error_code="NotARepo")
        try:
            status = client.status()
            lines = [
                f"Branch: {status.branch}",
                f"Ahead/Behind: +{status.ahead}/-{status.behind}",
                f"Modified: {', '.join(status.modified) if status.modified else 'none'}",
                f"Untracked: {', '.join(status.untracked) if status.untracked else 'none'}",
            ]
            return self.success("\n".join(lines), details=status.__dict__)
        except Exception as exc:
            return self.failure(str(exc))


def create_plugin(_manifest: dict[str, Any]) -> GitPlugin:
    return GitPlugin()
