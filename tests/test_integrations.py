"""Tests for built-in TARNO integrations loaded as plugins."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from tarno.ai.tool_registry import ToolRegistry
from tarno.integrations.calendar_email.client import CalendarClient
from tarno.integrations.discord.client import DiscordClientConfig, DiscordClientModule
from tarno.integrations.git.client import GitClient
from tarno.integrations.minecraft.client import MinecraftVoiceConfig, MinecraftVoiceModule
from tarno.integrations.smart_home.client import HomeAssistantBackend, SmartHomeClient
from tarno.plugins.manager import PluginManager

_INTEGRATIONS_DIR = Path(__file__).resolve().parent.parent / "tarno" / "integrations"


class MinecraftClientTests(unittest.TestCase):
    """Tests for the Minecraft voice mod client."""

    def test_default_config(self):
        cfg = MinecraftVoiceConfig()
        self.assertFalse(cfg.enabled)

    def test_module_connect(self):
        cfg = MinecraftVoiceConfig(enabled=True, host="127.0.0.1", port=19999)
        mod = MinecraftVoiceModule(cfg)
        # Without a real Minecraft mod, connect returns False without crashing.
        result = mod.connect()
        self.assertIsInstance(result, bool)


class GitClientTests(unittest.TestCase):
    """Tests for the Git integration client."""

    def test_not_a_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = GitClient(tmp)
            self.assertFalse(client.is_repo())

    def test_status_in_empty_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            import subprocess
            subprocess.run(["git", "init"], cwd=tmp, check=True, capture_output=True)
            client = GitClient(tmp)
            self.assertTrue(client.is_repo())
            status = client.status()
            self.assertIn(status.branch, {"master", "main", "HEAD"})


class PluginIntegrationTests(unittest.TestCase):
    """Tests that built-in integration plugins load correctly."""

    def _load_all(self) -> tuple[ToolRegistry, PluginManager]:
        registry = ToolRegistry()
        manager = PluginManager(registry)
        loaded = manager.load_from_directory(_INTEGRATIONS_DIR)
        self.assertGreaterEqual(loaded, 4)
        return registry, manager

    def test_minecraft_tools_present(self):
        registry, _ = self._load_all()
        names = [t["name"] for t in registry.get_tool_schemas()]
        self.assertIn("minecraft_connect", names)
        self.assertIn("minecraft_ptt", names)

    def test_discord_tools_present(self):
        registry, _ = self._load_all()
        names = [t["name"] for t in registry.get_tool_schemas()]
        self.assertIn("discord_mute", names)
        self.assertIn("discord_ptt", names)

    def test_git_tools_present(self):
        registry, _ = self._load_all()
        names = [t["name"] for t in registry.get_tool_schemas()]
        self.assertIn("git_status", names)

    def test_smart_home_tools_present(self):
        registry, _ = self._load_all()
        names = [t["name"] for t in registry.get_tool_schemas()]
        self.assertIn("smart_home_discover", names)
        self.assertIn("smart_home_set_state", names)

    def test_calendar_email_tools_present(self):
        registry, _ = self._load_all()
        names = [t["name"] for t in registry.get_tool_schemas()]
        self.assertIn("calendar_today", names)
        self.assertIn("email_unread", names)


class DiscordClientTests(unittest.TestCase):
    """Tests for the Discord client control module."""

    def test_push_to_talk(self):
        cfg = DiscordClientConfig(enabled=True, ptt_key="f13")
        client = DiscordClientModule(cfg)
        with mock.patch("pynput.keyboard.Controller") as mock_controller:
            instance = mock_controller.return_value
            result = client.push_to_talk(True)
            self.assertIn("gedrückt", result.lower())
            instance.press.assert_called()


class SmartHomeTests(unittest.TestCase):
    """Tests for the smart home abstraction."""

    def test_client_discovery(self):
        client = SmartHomeClient()
        backend = mock.Mock(spec=HomeAssistantBackend)
        backend.discover.return_value = [
            mock.Mock(id="light.salon", name="Salon", room="Wohnzimmer", device_type="light", state={"state": "on"})
        ]
        client.add_backend(backend)
        devices = client.discover()
        self.assertEqual(len(devices), 1)

    def test_set_state_delegates(self):
        client = SmartHomeClient()
        backend = mock.Mock(spec=HomeAssistantBackend)
        backend.is_available.return_value = True
        backend.set_state.return_value = True
        client.add_backend(backend)
        self.assertTrue(client.set_state("light.salon", "state", True))


class CalendarClientTests(unittest.TestCase):
    """Tests for the calendar ICS client."""

    def test_list_events_from_ics(self):
        with tempfile.TemporaryDirectory() as tmp:
            ics = Path(tmp) / "calendar.ics"
            start = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=1)
            ics.write_text(
                f"BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\n"
                f"DTSTART:{start.strftime('%Y%m%dT%H%M%S')}\n"
                f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}\n"
                f"SUMMARY:Test-Event\n"
                f"END:VEVENT\nEND:VCALENDAR\n",
                encoding="utf-8",
            )
            client = CalendarClient(ics)
            events = client.list_events(days=1)
            self.assertTrue(any("Test-Event" in e.summary for e in events))


if __name__ == "__main__":
    unittest.main()
