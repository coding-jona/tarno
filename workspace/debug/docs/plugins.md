# TARNO Plugin Developer Guide

TARNO loads external integrations as plugins. The core engine never imports integration code directly; plugins are discovered at runtime by the `PluginManager`.

## Plugin Layout

A plugin is a directory with at least two files:

```
my_plugin/
├── plugin.yaml       # manifest
└── plugin.py         # entrypoint
```

## Manifest (`plugin.yaml`)

```yaml
name: my_plugin
version: "1.0.0"
entrypoint: plugin.py
dependencies:
  - requests
config:
  api_key: null
```

- `name` and `version` are required.
- `dependencies` lists Python modules that must be importable. Missing dependencies are logged but the plugin may still load if it handles their absence.
- `config` is passed to the plugin via `context["config"]`.

## Minimal Plugin

```python
from tarno.ai.tool_registry import ToolDefinition
from tarno.core.action_result import ActionResult
from tarno.plugins.base import BasePlugin

class MyPlugin(BasePlugin):
    name = "my_plugin"
    version = "1.0.0"

    def get_tools(self):
        return [
            ToolDefinition(
                name="my_tool",
                description="Does something useful.",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                handler=self._my_tool,
            ),
        ]

    def _my_tool(self, query: str):
        return ActionResult(success=True, message=f"Result for {query}")

def create_plugin(manifest):
    return MyPlugin()
```

## Lifecycle

- `load(context)` — called once when the plugin is loaded.
- `on_load()` — override to read config, open connections, etc.
- `is_available()` — return `False` if the plugin cannot run in the current environment.
- `unload()` / `on_unload()` — called when the plugin is removed or the engine shuts down.

## Tool Handlers

Tool handlers should return `ActionResult`:

```python
from tarno.core.action_result import ActionResult

def handler(query: str) -> ActionResult:
    try:
        data = fetch(query)
        return ActionResult(success=True, message=f"Found {len(data)} items")
    except Exception as exc:
        return ActionResult(success=False, message=str(exc), error_code="FetchError")
```

## Security & Permissions

- Call `self.audit(action, details)` for every security-relevant operation.
- Use `self.require_permission(permission, target)` to integrate with the permission system.
- Never log secrets; the logging pipeline supports PII redaction.

## Installation

Drop the plugin directory into `~/.tarno/plugins/` or add it to `config.plugins.directories`. Built-in integrations live in `tarno/integrations/` and are loaded automatically.
