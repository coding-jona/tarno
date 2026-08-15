"""MeshRouter - the 4-scenario hub failover state machine from the original
spec, implemented as an explicit state machine (not implicit branching) so
transitions are debounced and always produce exactly one
MeshHubChangedEvent/MeshScenarioChangedEvent per real change.

Scenarios:
    FULL_MESH    - Hub-Handy reachable -> PC is MQTT client only, no local
                   broker.
    PC_FALLBACK  - Hub-Handy unreachable, Zweitgeraet (and/or ESP32) still
                   reachable -> PC starts the embedded broker, absorbs hub
                   duties.
    SOLO_PC      - neither hub nor secondary phone reachable -> PC only
                   consumes whatever ESP32 telemetry arrives (if any);
                   degrades cleanly, never errors.
    MOBILE_ONLY  - not a live PC-side state (it means "TARNO isn't running"
                   at all) - handled as a one-time sync-on-boot step in
                   client.py instead of a runtime transition here.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Callable

from tarno_backend.integrations.mesh.broker import EmbeddedMqttBroker
from tarno_backend.integrations.mesh.heartbeat import ESP32, HeartbeatMonitor
from tarno_backend.integrations.mesh.mqtt_bridge import MqttBridge
from tarno_backend.integrations.mesh.payload import MeshEvent

log = logging.getLogger(__name__)

FULL_MESH = "FULL_MESH"
PC_FALLBACK = "PC_FALLBACK"
SOLO_PC = "SOLO_PC"


@dataclass
class ScenarioTransition:
    previous: str
    current: str
    reason: str


class MeshRouter:
    """Owns node-presence tracking and the active-hub decision, and starts/
    stops the embedded broker accordingly. Deliberately synchronous/simple -
    called from a periodic tick thread owned by client.py, not its own loop,
    matching ProactiveEngine's tick-driven design rather than adding a
    second independent polling loop."""

    def __init__(
        self,
        heartbeat: HeartbeatMonitor,
        embedded_broker: EmbeddedMqttBroker,
        hub_bridge: MqttBridge,
        on_transition: Callable[[ScenarioTransition], None] | None = None,
        hub_node_match: str = "WIKO",
        secondary_node_match: str = "ZTE",
    ) -> None:
        self._heartbeat = heartbeat
        self._broker = embedded_broker
        self._hub_bridge = hub_bridge
        self._on_transition = on_transition
        self._scenario = SOLO_PC  # conservative starting assumption until first tick
        self._lock = threading.Lock()
        # Konfigurierbar statt hart auf ein bestimmtes Handymodell verdrahtet
        # (siehe MeshConfig.hub_node_match/secondary_node_match) - jeder
        # Nutzer traegt hier ein, was SEINE Handys als sender_node broadcasten.
        self._hub_node_match = hub_node_match.upper()
        self._secondary_node_match = secondary_node_match.upper()

    @property
    def scenario(self) -> str:
        """Currently active scenario (FULL_MESH / PC_FALLBACK / SOLO_PC)."""
        with self._lock:
            return self._scenario

    def record_event(self, event: MeshEvent) -> None:
        """Feed a parsed telemetry/heartbeat packet into presence tracking."""
        node = self._classify_sender(event.sender_node)
        if node is not None:
            self._heartbeat.mark_seen(node)

    def _classify_sender(self, sender_node: str) -> str | None:
        """Map a raw sender_node string (e.g. "ZTE_BLADE_V70") to the
        presence-tracking key it counts as, or None if it matches neither
        the configured hub, secondary, nor an ESP32 scanner."""
        upper = sender_node.upper()
        # Track presence under the configured match string itself (not a
        # fixed canonical label) so mark_seen()/is_online() agree with
        # whatever hub_node_match/secondary_node_match this instance was
        # configured with - a user with a different phone brand than the
        # default WIKO/ZTE still gets consistent tracking.
        if self._hub_node_match in upper:
            return self._hub_node_match
        if "ESP32" in upper:
            return ESP32
        if self._secondary_node_match in upper:
            return self._secondary_node_match
        return None

    def tick(self) -> None:
        """Re-evaluate which scenario applies and act on a change. Call this
        periodically (driven by client.py's heartbeat-interval timer)."""
        hub_online = self._heartbeat.is_online(self._hub_node_match)
        secondary_online = self._heartbeat.is_online(self._secondary_node_match)

        if hub_online:
            new_scenario = FULL_MESH
        elif secondary_online:
            new_scenario = PC_FALLBACK
        else:
            new_scenario = SOLO_PC

        with self._lock:
            previous = self._scenario
            if new_scenario == previous:
                return
            self._scenario = new_scenario

        self._apply_scenario(previous, new_scenario)

    def _apply_scenario(self, previous: str, current: str) -> None:
        """Side effects of a real scenario change: start/stop the embedded
        broker as needed and notify the on_transition callback."""
        reason = f"hub_online={self._heartbeat.is_online(self._hub_node_match)}, secondary_online={self._heartbeat.is_online(self._secondary_node_match)}"
        log.info("Mesh-Szenario-Wechsel: %s -> %s (%s)", previous, current, reason)

        if current == PC_FALLBACK and previous != PC_FALLBACK:
            self._broker.start()
        elif current != PC_FALLBACK and previous == PC_FALLBACK:
            self._broker.stop()

        if self._on_transition is not None:
            try:
                self._on_transition(ScenarioTransition(previous=previous, current=current, reason=reason))
            except Exception:
                log.exception("Mesh-Router: on_transition-Callback fehlgeschlagen")
