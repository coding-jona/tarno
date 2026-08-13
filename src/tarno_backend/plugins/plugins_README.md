# `tarno_backend/plugins/` — plugin system

Generic discovery/lifecycle machinery for extending TARNO with external
tools. This is the *mechanism*; the concrete built-in plugins that use it
live in `tarno_backend/integrations/` (Discord, Minecraft, Git, smart home,
calendar/email — see `integrations_README.md`).

## Files

- **`plugin.py`**: the plugin interface every plugin must implement.
- **`base.py`**: base class and shared helpers for production-ready plugins
  (logging, config access, tool registration boilerplate).
- **`manager.py`**: `PluginManager` — discovers plugins from a directory
  (`load_from_directory()`), instantiates them, and registers their tools
  with a `ToolRegistry`.

## Cross-references

- Concrete plugins built on this: `tarno_backend/integrations/` (see
  `integrations_README.md`)
- Tools plugins register into: `tarno_backend/ai/tool_registry.py` (see
  `ai_README.md`)
- Exercised together in [`workspace/debug/tests/test_integrations.py`](../../../workspace/debug/tests/test_integrations.py)
