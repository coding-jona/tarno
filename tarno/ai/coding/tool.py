"""coding_task tool registration helper."""

from __future__ import annotations

from tarno.ai.tool_registry import ToolDefinition
from tarno.ai.coding.agent import CodingAgent


def build_coding_task_tool(coding_agent: CodingAgent) -> ToolDefinition:
    """Return the ``coding_task`` ToolDefinition wired to ``coding_agent``."""
    return ToolDefinition(
        name="coding_task",
        description=(
            "Führt einen Coding-Task im aktiven Workspace aus. "
            "Kann Dateien analysieren oder editieren. "
            "Im read_only-Modus werden keine Änderungen geschrieben."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Aufgabenbeschreibung für den Coding-Agenten.",
                },
                "file_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Optionale relative oder absolute Dateipfade als Kontext."
                    ),
                },
                "read_only": {
                    "type": "boolean",
                    "description": (
                        "Wenn true, nur analysieren, nicht editieren. "
                        "Überschreibt den Autonomie-Modus."
                    ),
                },
            },
            "required": ["prompt"],
        },
        handler=coding_agent.execute_task,
    )
