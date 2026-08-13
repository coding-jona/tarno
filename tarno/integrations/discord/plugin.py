"""TARNO plugin for local Discord client control."""

from __future__ import annotations

from typing import Any

from tarno.ai.tool_registry import ToolDefinition
from tarno.core.action_result import ActionResult
from tarno.integrations.discord.client import DiscordClientConfig, DiscordClientModule
from tarno.plugins.base import BasePlugin


class DiscordPlugin(BasePlugin):
    """Provides tools to mute/unmute or PTT-control a local Discord client."""

    name = "discord_client"
    version = "1.0.0"
    dependencies: list[str] = []

    def __init__(self) -> None:
        super().__init__()
        self._client: DiscordClientModule | None = None

    def on_load(self) -> None:
        config = self._context.get("config") if self._context else {}
        if isinstance(config, dict):
            cfg = DiscordClientConfig(
                enabled=config.get("enabled", False),
                ptt_key=config.get("ptt_key"),
                virtual_cable=config.get("virtual_cable"),
            )
        else:
            cfg = DiscordClientConfig()
        self._client = DiscordClientModule(cfg)
        self.audit("loaded", {"enabled": cfg.enabled})

    def on_unload(self) -> None:
        self._client = None

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="discord_mute",
                description="Stummschaltung des lokalen Discord-Clients umschalten.",
                input_schema={
                    "type": "object",
                    "properties": {"muted": {"type": "boolean"}},
                    "required": ["muted"],
                },
                handler=self._mute,
            ),
            ToolDefinition(
                name="discord_ptt",
                description="Push-to-Talk in Discord drücken oder loslassen.",
                input_schema={
                    "type": "object",
                    "properties": {"active": {"type": "boolean"}},
                    "required": ["active"],
                },
                handler=self._ptt,
            ),
        ]

    def _mute(self, muted: bool) -> ActionResult:
        if self._client is None:
            return self.failure("Plugin nicht geladen")
        result = self._client.set_mute(muted)
        return self.success(result)

    def _ptt(self, active: bool) -> ActionResult:
        if self._client is None:
            return self.failure("Plugin nicht geladen")
        result = self._client.push_to_talk(active)
        return self.success(result)


def create_plugin(_manifest: dict[str, Any]) -> DiscordPlugin:
    return DiscordPlugin()
