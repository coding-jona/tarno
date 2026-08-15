"""MeshObserver - implements the ProactiveObserver protocol so mesh hub
transitions surface as spoken commentary through TARNO's existing
proactive-engine -> _on_proactive_trigger -> event_bus/TTS path (see
tarno/core/proactive_engine.py, tarno/core/engine.py:_on_proactive_trigger).

Subscribes to MeshScenarioChangedEvent on the event bus and buffers the
latest unreported transition; ProactiveEngine's tick calls check(), which
drains the buffer. This means at most one draft per real transition,
regardless of the proactive tick rate - no polling of router state directly,
matching the "never spam on a sustained condition" intent already used by
SystemObserver/UserBehaviorObserver's cooldown logic."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone

from tarno_backend.core.events import EventBus, MeshScenarioChangedEvent
from tarno_backend.core.proactive_engine import ProactiveDraft
from tarno_backend.integrations.mesh import cloud_client, persona
from tarno_backend.integrations.mesh.router import FULL_MESH, PC_FALLBACK, SOLO_PC

log = logging.getLogger(__name__)

# Mappt Router-Szenarien auf persona.py-Event-Typen ("The Sarcastic Observer" -
# eigener Ton NUR fuer diese autonomen Kommentare, siehe persona.py-Modul-
# Docstring). Ersetzt die vorherige statische _SCENARIO_MESSAGES-Map.
_SCENARIO_EVENT_TYPES: dict[str, str] = {
    PC_FALLBACK: "HUB_FALLBACK_PC",
    FULL_MESH: "HUB_FULL_MESH",
    SOLO_PC: "HUB_SOLO_PC",
}


class MeshObserver:
    """One autonomous check per ProactiveEngine tick (Phase-3-Protokoll)."""

    name = "mesh"

    def __init__(self, event_bus: EventBus, score: int = 90) -> None:
        self._score = score
        self._lock = threading.Lock()
        self._pending: MeshScenarioChangedEvent | None = None
        event_bus.subscribe(MeshScenarioChangedEvent, self._on_scenario_changed)

    def _on_scenario_changed(self, event: MeshScenarioChangedEvent) -> None:
        with self._lock:
            self._pending = event

    def check(self) -> ProactiveDraft | None:
        with self._lock:
            event = self._pending
            self._pending = None

        if event is None:
            return None

        event_type = _SCENARIO_EVENT_TYPES.get(event.scenario)
        if event_type is None:
            log.debug("Mesh-Observer: unbekanntes Szenario %s, kein Kommentar", event.scenario)
            return None

        return ProactiveDraft(source=self.name, message=persona.comment(event_type), score=self._score)


_ONLINE_THRESHOLD_SECONDS = 90.0  # gleicher Schwellenwert wie MeshDashboardPage.OnlineThreshold (WinUI3)


def _is_online(device: dict) -> bool:
    last_seen = device.get("last_seen_at")
    if not last_seen:
        return False
    try:
        seen_at = datetime.fromisoformat(last_seen)
    except ValueError:
        return False
    if seen_at.tzinfo is None:
        seen_at = seen_at.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - seen_at).total_seconds() < _ONLINE_THRESHOLD_SECONDS


class CloudMeshObserver:
    """Zweiter, unabhaengiger ProactiveObserver - ergaenzt MeshObserver (oben,
    reagiert auf den LOKALEN UDP/MQTT-Hub) um Sprachkommentare zu den NEUEN
    Cloud-Tracking-Geraeten (Handys, ESP32 - siehe cloud_client.py). Der
    Tarno-Server hat keinen Event-Bus/Push-Mechanismus zum PC, deshalb Polling
    statt Subscription wie bei MeshObserver - aber gedrosselt auf einmal pro
    _poll_interval_seconds (deutlich seltener als der ProactiveEngine-Tick),
    damit nicht bei jedem 10s-Tick ein HTTP-Request an den eigenen VPS geht.

    Meldet nur ECHTE Uebergaenge (online<->offline pro Geraet, oder ein
    frischer Abfall unter die Akku-Kritisch-Schwelle), keine Dauerzustaende -
    sonst wuerde ein dauerhaft offline/leeres Geraet bei jedem Poll erneut
    einen Kommentar ausloesen. Erster Poll nach Start etabliert nur den
    Ausgangszustand (kein Kommentar), sonst wuerde ein App-Neustart bei
    laengst bekannten Geraeten faelschlich "ist jetzt online" ankuendigen.

    Nutzt persona.py ("The Sarcastic Observer") statt neutraler Saetze - wie
    MeshObserver oben, eigener Ton nur fuer diese autonomen Kommentare."""

    name = "mesh_cloud"

    # Hysterese (kritisch < 15%, wieder "entwarnt" erst ab > 25%) - verhindert,
    # dass ein Akkustand, der genau um 15% herum schwankt, bei jedem Poll
    # erneut den BATTERY_CRITICAL-Kommentar ausloest ("Flapping").
    _BATTERY_CRITICAL_PERCENT = 15
    _BATTERY_RECOVERED_PERCENT = 25

    def __init__(self, server_url: str, score: int = 70, poll_interval_seconds: float = 60.0) -> None:
        self._server_url = server_url
        self._score = score
        self._poll_interval_seconds = poll_interval_seconds
        self._last_poll_monotonic: float | None = None
        self._known_online: dict[str, bool] = {}
        self._battery_critical: dict[str, bool] = {}
        self._initialized = False

    def check(self) -> ProactiveDraft | None:
        """Poll the Tarno-Server once (throttled to _poll_interval_seconds)
        and return a draft for the first real online/offline or
        battery-critical transition found, if any. Returns None on a
        throttled/failed/no-op poll."""
        now = time.monotonic()
        if self._last_poll_monotonic is not None and now - self._last_poll_monotonic < self._poll_interval_seconds:
            return None
        self._last_poll_monotonic = now

        devices, error = cloud_client.fetch_devices(self._server_url)
        if devices is None:
            log.debug("CloudMeshObserver: Poll uebersprungen (%s)", error)
            return None

        # Only the first transition found becomes the spoken draft (one
        # comment per tick, matching every other observer) - both checks
        # below always run for every device regardless (they update
        # per-device state as a side effect), so a message found early
        # doesn't leave later devices' online/battery state stale for the
        # next poll.
        message: str | None = None
        for device in devices:
            device_id = device.get("id")
            if not device_id:
                continue
            name = device.get("name", "Geraet")

            online_message = self._check_online_transition(device_id, name, device)
            battery_message = self._check_battery_transition(device_id, name, device)
            if message is None:
                message = online_message or battery_message

        self._initialized = True
        if message is None:
            return None
        return ProactiveDraft(source=self.name, message=message, score=self._score)

    def _check_online_transition(self, device_id: str, name: str, device: dict) -> str | None:
        """Update known-online state for one device and return a spoken
        comment if it just flipped online/offline. Silent on the very first
        poll (self._initialized False) so a fresh app start doesn't
        misreport already-known devices as newly online."""
        online = _is_online(device)
        previous_online = self._known_online.get(device_id)
        self._known_online[device_id] = online
        if not self._initialized or previous_online is None or previous_online == online:
            return None
        event_type = "DEVICE_ONLINE" if online else "DEVICE_OFFLINE"
        return persona.comment(event_type, name=name)

    def _check_battery_transition(self, device_id: str, name: str, device: dict) -> str | None:
        """Update battery-critical hysteresis state for one device and
        return a spoken comment on a fresh drop below the critical
        threshold. See _BATTERY_CRITICAL_PERCENT/_BATTERY_RECOVERED_PERCENT
        for the hysteresis band."""
        level = self._battery_level(device)
        if level is None:
            return None

        was_critical = self._battery_critical.get(device_id, False)
        now_critical = level < self._BATTERY_CRITICAL_PERCENT
        now_recovered = level >= self._BATTERY_RECOVERED_PERCENT
        if now_critical:
            self._battery_critical[device_id] = True
        elif now_recovered:
            self._battery_critical[device_id] = False

        if self._initialized and not was_critical and now_critical:
            return persona.comment("BATTERY_CRITICAL", name=name, level=level)
        return None

    @staticmethod
    def _battery_level(device: dict) -> int | None:
        """Extract the last-reported battery percentage, if any."""
        payloads = device.get("last_payloads") or {}
        battery = payloads.get("battery_network_status")
        if not battery:
            return None
        level = battery.get("payload", {}).get("battery_level")
        return level if isinstance(level, int) else None
