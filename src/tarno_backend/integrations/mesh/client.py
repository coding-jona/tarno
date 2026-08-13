"""MeshClient - facade tying together the UDP listener, embedded broker,
hub MQTT bridge, heartbeat tracking and router into one component that
plugin.py starts/stops from on_load()/on_unload().

Also handles the one deferred piece of wiring that can't happen at plugin-
load time: TarnoEngine._load_plugins() runs before self._proactive_engine is
constructed (verified in engine.py), so attaching MeshObserver has to wait a
short, bounded amount of time after on_load() - matching the same live-
attach mechanism already used by set_vision_enabled() elsewhere in the
codebase, not a new pattern."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from tarno_backend.core.config import MeshConfig
from tarno_backend.core.events import MeshHubChangedEvent, MeshNodeSeenEvent, MeshScenarioChangedEvent
from tarno_backend.integrations.mesh.broker import EmbeddedMqttBroker
from tarno_backend.integrations.mesh.heartbeat import HeartbeatMonitor
from tarno_backend.integrations.mesh.mqtt_bridge import MqttBridge
from tarno_backend.integrations.mesh.observer import MeshObserver
from tarno_backend.integrations.mesh.payload import MeshEvent
from tarno_backend.integrations.mesh.router import MeshRouter, ScenarioTransition
from tarno_backend.integrations.mesh.udp_listener import UdpBroadcastListener

log = logging.getLogger(__name__)

_OBSERVER_ATTACH_RETRY_INTERVAL = 0.1
_OBSERVER_ATTACH_MAX_WAIT = 5.0


class MeshClient:
    def __init__(self, config: MeshConfig, engine: Any | None) -> None:
        self._config = config
        self._engine = engine

        self._heartbeat = HeartbeatMonitor(heartbeat_interval_seconds=config.heartbeat_interval_seconds)
        self._broker = EmbeddedMqttBroker(port=config.mqtt_port)
        self._hub_bridge = MqttBridge()
        self._router = MeshRouter(
            heartbeat=self._heartbeat,
            embedded_broker=self._broker,
            hub_bridge=self._hub_bridge,
            on_transition=self._on_transition,
            hub_node_match=config.hub_node_match,
            secondary_node_match=config.secondary_node_match,
        )
        self._listener = UdpBroadcastListener(port=config.udp_port, on_event=self._on_udp_event)
        self._observer = MeshObserver(engine.event_bus, score=config.score_threshold + 1) if engine is not None else None

        self._tick_thread: threading.Thread | None = None
        self._tick_stop = threading.Event()
        self._attach_thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True

        self._listener.start()

        if self._config.hub_host:
            connected = self._hub_bridge.connect(self._config.hub_host, self._config.mqtt_port)
            if not connected:
                log.info(
                    "Hub-Handy (%s) nicht erreichbar - Mesh startet im PC_FALLBACK-Pfad, "
                    "sobald ein anderer Node gesehen wird.",
                    self._config.hub_host,
                )

        self._tick_stop.clear()
        self._tick_thread = threading.Thread(target=self._tick_loop, daemon=True, name="MeshRouterTick")
        self._tick_thread.start()

        if self._engine is not None and self._observer is not None:
            self._attach_thread = threading.Thread(
                target=self._attach_observer_when_ready, daemon=True, name="MeshObserverAttach"
            )
            self._attach_thread.start()

        log.info("Mesh-Client gestartet (UDP-Port %d, MQTT-Port %d)", self._config.udp_port, self._config.mqtt_port)

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._tick_stop.set()
        if self._tick_thread and self._tick_thread.is_alive():
            self._tick_thread.join(timeout=2.0)
        self._listener.stop()
        self._hub_bridge.disconnect()
        self._broker.stop()
        log.info("Mesh-Client gestoppt")

    def _on_udp_event(self, event: MeshEvent) -> None:
        self._router.record_event(event)
        if self._engine is not None:
            self._engine.event_bus.publish(
                MeshNodeSeenEvent(
                    sender_node=event.sender_node,
                    event_type=event.event_type,
                    payload=event.payload,
                    timestamp=event.timestamp,
                )
            )

    def _on_transition(self, transition: ScenarioTransition) -> None:
        if self._engine is None:
            return
        active_hub = "PC_FALLBACK" if transition.current == "PC_FALLBACK" else (
            "HUB" if transition.current == "FULL_MESH" else "NONE"
        )
        self._engine.event_bus.publish(MeshHubChangedEvent(active_hub=active_hub, reason=transition.reason))
        self._engine.event_bus.publish(
            MeshScenarioChangedEvent(scenario=transition.current, previous=transition.previous)
        )

    def _tick_loop(self) -> None:
        interval = self._heartbeat.interval_seconds
        while self._running and not self._tick_stop.is_set():
            self._router.tick()
            if self._tick_stop.wait(interval):
                break

    def _attach_observer_when_ready(self) -> None:
        waited = 0.0
        while waited < _OBSERVER_ATTACH_MAX_WAIT:
            proactive_engine = getattr(self._engine, "_proactive_engine", None)
            if proactive_engine is not None:
                proactive_engine.add_observer(self._observer)
                log.info("MeshObserver an ProactiveEngine angehängt")
                return
            time.sleep(_OBSERVER_ATTACH_RETRY_INTERVAL)
            waited += _OBSERVER_ATTACH_RETRY_INTERVAL
        log.warning(
            "ProactiveEngine nach %.0fs nicht verfügbar - Mesh-Sprachkommentare deaktiviert "
            "(Telemetrie/Router laufen weiter unabhängig davon)",
            _OBSERVER_ATTACH_MAX_WAIT,
        )
