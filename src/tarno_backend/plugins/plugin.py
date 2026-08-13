"""Plugin interface for TARNO extensions."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from tarno_backend.ai.tool_registry import ToolDefinition


@runtime_checkable
class TarnoPlugin(Protocol):
    """Protocol that all TARNO plugins must implement."""

    name: str
    version: str

    def load(self, context: dict[str, Any] | None = None) -> None:
        """Called when the plugin is loaded."""
        ...

    def unload(self) -> None:
        """Called when the plugin is unloaded."""
        ...

    def get_tools(self) -> list[ToolDefinition]:
        """Return the list of ToolDefinitions provided by this plugin."""
        ...

    def is_available(self) -> bool:
        """Return True if the plugin can function in the current environment."""
        ...
