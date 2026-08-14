"""Tests for the plugin architecture."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from tarno_backend.ai.tool_registry import ToolDefinition, ToolRegistry
from tarno_backend.plugins.manager import PluginManager


class PluginManagerTests(unittest.TestCase):
    """Tests for plugin discovery and lifecycle."""

    def _write_dummy_plugin(self, directory: Path, name: str) -> None:
        plugin_dir = directory / name
        plugin_dir.mkdir(parents=True)
        manifest = {"name": name, "version": "1.0.0", "entrypoint": "plugin.py"}
        (plugin_dir / "plugin.yaml").write_text(
            yaml.safe_dump(manifest), encoding="utf-8"
        )
        (plugin_dir / "plugin.py").write_text(
            "from tarno_backend.ai.tool_registry import ToolDefinition\n"
            "class DummyPlugin:\n"
            "    name = 'dummy'\n"
            "    version = '1.0.0'\n"
            "    def load(self, context): pass\n"
            "    def unload(self): pass\n"
            "    def is_available(self): return True\n"
            "    def get_tools(self):\n"
            "        return [ToolDefinition(\n"
            f"            name='{name}_tool',\n"
            "            description='test',\n"
            "            input_schema={{'type': 'object', 'properties': {{}}}},\n"
            "            handler=lambda: 'ok'\n"
            "        )]\n"
            "plugin = DummyPlugin()\n",
            encoding="utf-8",
        )

    def test_load_from_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "plugins"
            self._write_dummy_plugin(plugin_dir, "demo")
            registry = ToolRegistry()
            manager = PluginManager(registry)
            loaded = manager.load_from_directory(plugin_dir)
            self.assertEqual(loaded, 1)
            self.assertIn("demo_tool", [t["name"] for t in registry.get_tool_schemas()])

    def test_unload_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "plugins"
            self._write_dummy_plugin(plugin_dir, "demo")
            registry = ToolRegistry()
            manager = PluginManager(registry)
            manager.load_from_directory(plugin_dir)
            self.assertTrue(registry.get("demo_tool") is not None)
            manager.unload("demo")
            self.assertIsNone(registry.get("demo_tool"))

    def test_invalid_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "plugins"
            bad_dir = plugin_dir / "bad"
            bad_dir.mkdir(parents=True)
            (bad_dir / "plugin.yaml").write_text(
                yaml.safe_dump({"name": "bad"}), encoding="utf-8"
            )
            (bad_dir / "plugin.py").write_text("plugin = None", encoding="utf-8")
            registry = ToolRegistry()
            manager = PluginManager(registry)
            loaded = manager.load_from_directory(plugin_dir)
            self.assertEqual(loaded, 0)

    def test_missing_dependencies_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "plugins"
            pdir = plugin_dir / "dep"
            pdir.mkdir(parents=True)
            manifest = {
                "name": "dep",
                "version": "1.0.0",
                "entrypoint": "plugin.py",
                "dependencies": ["definitely_not_installed_module_xyz"],
            }
            (pdir / "plugin.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
            (pdir / "plugin.py").write_text(
                "from tarno_backend.ai.tool_registry import ToolDefinition\n"
                "class DepPlugin:\n"
                "    name = 'dep'\n"
                "    def load(self, context): pass\n"
                "    def unload(self): pass\n"
                "    def is_available(self): return True\n"
                "    def get_tools(self):\n"
                "        return []\n"
                "plugin = DepPlugin()\n",
                encoding="utf-8",
            )
            registry = ToolRegistry()
            manager = PluginManager(registry)
            manager.load_from_directory(plugin_dir)
            missing = manager.missing_dependencies()
            self.assertIn("dep", missing)
            self.assertIn("definitely_not_installed_module_xyz", missing["dep"])


if __name__ == "__main__":
    unittest.main()
