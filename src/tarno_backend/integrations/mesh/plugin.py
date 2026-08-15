"""TARNO plugin for the Dynamic Hybrid Mesh (secondary phone, ESP32-S3 scanner,
hub phone). Follows the same structure as
tarno/integrations/smart_home/plugin.py."""

from __future__ import annotations

import datetime
from typing import Any

from tarno_backend.ai.tool_registry import ToolDefinition
from tarno_backend.core.action_result import ActionResult
from tarno_backend.core.config import MeshConfig
from tarno_backend.integrations.mesh import cloud_client
from tarno_backend.integrations.mesh.client import MeshClient
from tarno_backend.plugins.base import BasePlugin

# Bewusst dieselbe kleine Zuordnungstabelle wie MeshDashboardPage.FriendlyAppName
# (WinUI3) und FriendlyAppName (Android) - rohe Android-Package-Namen sind fuer
# TARNOs gesprochene Antwort nicht brauchbar.
_KNOWN_APP_NAMES: dict[str, str] = {
    "com.zhiliaoapp.musically": "TikTok",
    "com.whatsapp": "WhatsApp",
    "com.instagram.android": "Instagram",
    "com.google.android.youtube": "YouTube",
    "com.google.android.apps.maps": "Google Maps",
    "com.android.chrome": "Chrome",
    "com.facebook.katana": "Facebook",
    "com.snapchat.android": "Snapchat",
    "com.spotify.music": "Spotify",
    "com.google.android.gm": "Gmail",
    "com.twitter.android": "X (Twitter)",
    "org.telegram.messenger": "Telegram",
    "com.discord": "Discord",
}


def _friendly_app_name(package_name: str) -> str:
    """Map an Android package name to a spoken-friendly app name, or return
    it unchanged if unknown."""
    return _KNOWN_APP_NAMES.get(package_name, package_name)


def _format_relative(iso_timestamp: str) -> str:
    """Turn an ISO-8601 sync timestamp into a short relative phrase
    ("vor 12s" / "vor 3min" / ...), falling back to an absolute date once
    it's more than two days old."""
    try:
        synced_at = datetime.datetime.fromisoformat(iso_timestamp)
    except ValueError:
        return "unbekannt"
    if synced_at.tzinfo is None:
        synced_at = synced_at.replace(tzinfo=datetime.timezone.utc)
    delta = datetime.datetime.now(datetime.timezone.utc) - synced_at
    seconds = delta.total_seconds()
    if seconds < 90:
        return f"vor {int(seconds)}s"
    if seconds < 90 * 60:
        return f"vor {int(seconds / 60)}min"
    if seconds < 48 * 3600:
        return f"vor {int(seconds / 3600)}h"
    return synced_at.astimezone().strftime("am %d.%m.%Y um %H:%M")


def _describe_device(device: dict[str, Any]) -> str:
    """Build one spoken-friendly summary line for a single cloud-tracked
    device from whatever payload types it has last reported (battery,
    location, foreground app) - missing payload types are simply skipped."""
    name = device.get("name", "?")
    kind = device.get("kind", "?")
    payloads: dict[str, Any] = device.get("last_payloads") or {}

    lines: list[str] = []

    battery = payloads.get("battery_network_status")
    if battery:
        p = battery.get("payload", {})
        level = p.get("battery_level")
        charging = p.get("is_charging")
        network = p.get("network_type", "?")
        charge_text = " (laedt)" if charging else ""
        lines.append(f"Akku {level}%{charge_text}, Netzwerk {network} ({_format_relative(battery.get('synced_at', ''))})")

    location = payloads.get("location")
    if location:
        p = location.get("payload", {})
        lat, lon = p.get("lat"), p.get("lon")
        if lat is not None and lon is not None:
            lines.append(f"Standort {lat:.4f}, {lon:.4f} ({_format_relative(location.get('synced_at', ''))})")

    app_usage = payloads.get("app_usage")
    if app_usage:
        p = app_usage.get("payload", {})
        pkg = p.get("foreground_package", "?")
        lines.append(f"Zuletzt aktive App: {_friendly_app_name(pkg)} ({_format_relative(app_usage.get('synced_at', ''))})")

    if not lines:
        lines.append("noch keine Tracking-Daten")

    return f"{name} ({kind}): " + "; ".join(lines)


class MeshPlugin(BasePlugin):
    """Aggregates mesh-node telemetry and reacts via TARNO's existing
    proactive-commentary/TTS path. Disabled unless `mesh.enabled` is set in
    TarnoConfig - adding this plugin package changes nothing for existing
    users by default."""

    name = "mesh"
    version = "1.0.0"
    dependencies: list[str] = []

    def __init__(self) -> None:
        super().__init__()
        self._client: MeshClient | None = None
        self._mesh_config: MeshConfig = MeshConfig()

    def on_load(self) -> None:
        """Start the local UDP/MQTT mesh client if mesh.enabled is set.
        The cloud device-tracking tool (mesh_device_status) works
        regardless of this flag - see the comment below."""
        config = self._context.get("config") if self._context else None
        self._mesh_config = getattr(config, "mesh", MeshConfig())

        # KERNPUNKT: cloud_server_url wird unabhaengig von mesh.enabled
        # gespeichert - der mesh_device_status-Tool-Call (Cloud-Tracking) ist
        # ein separates Feature vom lokalen UDP/MQTT-Hub unten und soll auch
        # nutzbar sein, wenn Letzterer per Kconfig/Settings deaktiviert ist.
        if not self._mesh_config.enabled:
            self.audit("skipped", {"reason": "mesh.enabled is False (lokaler Hub) - Cloud-Tool bleibt trotzdem nutzbar"})
            return

        engine = self._context.get("engine") if self._context else None
        self._client = MeshClient(self._mesh_config, engine)
        self._client.start()
        self.audit("loaded", {"udp_port": self._mesh_config.udp_port, "mqtt_port": self._mesh_config.mqtt_port})

    def on_unload(self) -> None:
        if self._client is not None:
            self._client.stop()
            self._client = None

    def is_available(self) -> bool:
        # Always "available" even with mesh.enabled=False - on_load() already
        # handles that as a no-op, so PluginManager doesn't need to treat a
        # disabled mesh feature as an unloadable/broken plugin.
        return True

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="mesh_status",
                description="Zeigt den aktuellen Status des Dynamic-Hybrid-Mesh (aktiver Hub, erreichbare Nodes).",
                input_schema={"type": "object", "properties": {}},
                handler=self._status,
            ),
            ToolDefinition(
                name="mesh_device_status",
                description=(
                    "Zeigt die aktuellen Tracking-Daten (Akku/Ladezustand, Standort, zuletzt genutzte App) "
                    "aller Handys und ESP32-Nodes, die im Tarno-Server-Account registriert sind - z.B. fuer "
                    "Fragen wie 'was geht gerade auf meinem Handy ab', 'wo ist mein Handy', 'ist mein Akku "
                    "leer', 'welche App nutze ich gerade'. Nutzt die Cloud-Sync-Daten (tarno.cousinsmp.de), "
                    "NICHT das lokale UDP-Mesh - siehe mesh_status fuer den lokalen Hub-Status."
                ),
                input_schema={"type": "object", "properties": {}},
                handler=self._device_status,
            ),
        ]

    def _status(self) -> ActionResult:
        """Tool handler for `mesh_status`: report the local UDP/MQTT
        router's current hub scenario."""
        if self._client is None:
            return self.success("Mesh ist deaktiviert (mesh.enabled = false).")
        scenario = self._client.scenario
        return self.success(f"Aktuelles Mesh-Szenario: {scenario}")

    def _device_status(self) -> ActionResult:
        """Tool handler for `mesh_device_status`: summarize the cloud-synced
        tracking data (battery, location, foreground app) for every device
        registered on the account."""
        devices, error = cloud_client.fetch_devices(self._mesh_config.cloud_server_url)
        if devices is None:
            return self.failure(error or "Cloud-Geraetestatus nicht abrufbar.")
        if not devices:
            return self.success("Noch keine Geraete im Tarno-Server-Account registriert.")
        summary = " | ".join(_describe_device(d) for d in devices)
        return self.success(summary)


def create_plugin(_manifest: dict[str, Any]) -> MeshPlugin:
    """Entry point PluginManager calls to instantiate this plugin."""
    return MeshPlugin()
