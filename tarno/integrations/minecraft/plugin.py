"""TARNO plugin for Minecraft Simple Voice Chat companion integration."""

from __future__ import annotations

from typing import Any

from tarno.ai.tool_registry import ToolDefinition
from tarno.core.action_result import ActionResult
from tarno.integrations.minecraft.client import MinecraftVoiceConfig, MinecraftVoiceModule
from tarno.plugins.base import BasePlugin


class MinecraftPlugin(BasePlugin):
    """Provides voice-control tools for a local Minecraft companion mod."""

    name = "minecraft_voice"
    version = "1.0.0"
    dependencies: list[str] = []

    def __init__(self) -> None:
        super().__init__()
        self._client: MinecraftVoiceModule | None = None

    def on_load(self) -> None:
        config = self._context.get("config") if self._context else {}
        if isinstance(config, dict):
            cfg = MinecraftVoiceConfig(
                enabled=config.get("enabled", False),
                host=config.get("host", "127.0.0.1"),
                port=config.get("port", 19999),
            )
        else:
            cfg = MinecraftVoiceConfig()
        self._client = MinecraftVoiceModule(cfg)
        self.audit("loaded", {"enabled": cfg.enabled})

    def on_unload(self) -> None:
        if self._client is not None:
            self._client.disconnect()
            self._client = None

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="minecraft_connect",
                description="Verbindet TARNO mit dem lokalen Minecraft Voice Mod.",
                input_schema={"type": "object", "properties": {}},
                handler=self._connect,
            ),
            ToolDefinition(
                name="minecraft_ptt",
                description="Aktiviert oder deaktiviert Push-to-Talk in Minecraft.",
                input_schema={
                    "type": "object",
                    "properties": {"active": {"type": "boolean"}},
                    "required": ["active"],
                },
                handler=self._ptt,
            ),
        ]

    def _connect(self) -> ActionResult:
        if self._client is None:
            return self.failure("Plugin nicht geladen")
        ok = self._client.connect()
        return self.success("Mit Minecraft Voice Mod verbunden") if ok else self.failure("Verbindung fehlgeschlagen")

    def _ptt(self, active: bool) -> ActionResult:
        if self._client is None:
            return self.failure("Plugin nicht geladen")
        ok = self._client.push_to_talk(active)
        state = "aktiviert" if active else "deaktiviert"
        return self.success(f"Push-to-Talk {state}") if ok else self.failure("PTT-Steuerung fehlgeschlagen")


def create_plugin(_manifest: dict[str, Any]) -> MinecraftPlugin:
    return MinecraftPlugin()
