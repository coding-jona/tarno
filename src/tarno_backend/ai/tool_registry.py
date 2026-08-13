"""Registry of tools that Claude can invoke via native tool_use."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from tarno_backend.core.action_result import ActionResult

log = logging.getLogger(__name__)

ToolHandler = Callable[..., Any]

# Block 5, Phase 42 ("harte Typprüfung"): LLM-generated tool arguments are
# untrusted input structurally, even after the content_filter's lexical scan -
# a wrong type (e.g. a list where a string was expected) could crash a
# handler or, worse, be silently coerced into something unintended. This is a
# small hand-rolled validator rather than the `jsonschema` package: every
# input_schema in this codebase only ever uses "type", "enum", "properties"
# and "required" - adding a full JSON-Schema-Draft implementation as a
# dependency for that subset would be more surface area than the problem needs.
_JSON_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
    "object": (dict,),
    "array": (list,),
    "null": (type(None),),
}

# Block 5, Phase 44 ("Excessive Agency" - Argumenten-Längen-Limits): a wildly
# oversized string argument (e.g. an injected multi-megabyte "path" or
# "command") is a resource-exhaustion/agency-scope-creep vector even if it
# passes type-checking. No legitimate tool call in this codebase needs a
# single string argument anywhere near this large.
MAX_STRING_ARG_LENGTH = 8192


def _validate_value(value: Any, schema: dict[str, Any], path: str) -> str | None:
    """Return an error message if *value* doesn't satisfy *schema*, else None."""
    expected_type = schema.get("type")
    if expected_type is not None:
        allowed = _JSON_TYPE_MAP.get(expected_type)
        if allowed is not None:
            # bool is a subclass of int in Python - explicitly reject it for
            # "number"/"integer" so a boolean doesn't silently pass as numeric.
            if expected_type in ("number", "integer") and isinstance(value, bool):
                return f"{path}: erwartet Typ '{expected_type}', bekam 'bool'"
            if not isinstance(value, allowed):
                return f"{path}: erwartet Typ '{expected_type}', bekam '{type(value).__name__}'"

    if isinstance(value, str) and len(value) > MAX_STRING_ARG_LENGTH:
        return f"{path}: Zeichenkette zu lang ({len(value)} > {MAX_STRING_ARG_LENGTH})"

    enum = schema.get("enum")
    if enum is not None and value not in enum:
        return f"{path}: '{value}' ist nicht in der erlaubten Liste {enum}"

    if expected_type == "object" and isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                return f"{path}: Pflichtfeld '{key}' fehlt"
        for key, sub_value in value.items():
            sub_schema = properties.get(key)
            if sub_schema is None:
                continue  # additionalProperties allowed (matches JSON-Schema default)
            error = _validate_value(sub_value, sub_schema, f"{path}.{key}" if path else key)
            if error:
                return error

    return None


def validate_tool_input(tool_input: dict[str, Any], input_schema: dict[str, Any]) -> str | None:
    """Validate a tool call's arguments against its declared input_schema.

    Returns a human-readable error string on the first violation found, or
    None if the input is valid.
    """
    return _validate_value(tool_input, input_schema, "")


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler


class ToolRegistry:
    """Collects tool definitions and dispatches tool calls."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool
        log.debug("Tool registriert: %s", tool.name)

    def unregister(self, name: str) -> bool:
        """Remove a tool by name. Returns True if it existed."""
        existed = name in self._tools
        self._tools.pop(name, None)
        return existed

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in self._tools.values()
        ]

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> ActionResult:
        tool = self._tools.get(tool_name)
        if tool is None:
            log.warning("Unbekanntes Tool: %s", tool_name)
            return ActionResult(
                success=False,
                message=f"Unbekanntes Tool: {tool_name}",
                error_code="ToolNotFound",
            )

        validation_error = validate_tool_input(tool_input, tool.input_schema)
        if validation_error is not None:
            log.warning("Tool-Argument-Validierung fehlgeschlagen für %s: %s", tool_name, validation_error)
            return ActionResult(
                success=False,
                message=f"Ungültige Argumente für '{tool_name}': {validation_error}",
                error_code="InvalidArguments",
            )

        # Nur tatsaechlich im input_schema deklarierte Argumente weitergeben - das
        # verhindert, dass das LLM zusaetzliche Keys (z. B. 'name') als kwargs an
        # den Handler durchreicht und Methoden ohne solche Parameter crashen.
        allowed = set(tool.input_schema.get("properties", {}).keys())
        kwargs = {k: v for k, v in tool_input.items() if k in allowed}

        log.info("Tool ausgeführt: %s(%s)", tool_name, kwargs)
        try:
            result = tool.handler(**kwargs)
            if isinstance(result, ActionResult):
                return result
            return ActionResult(success=True, message=str(result))
        except Exception as exc:
            log.exception("Tool-Fehler: %s", tool_name)
            return ActionResult.from_exception(exc)
