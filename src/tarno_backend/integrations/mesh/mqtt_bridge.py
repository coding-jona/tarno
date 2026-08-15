"""MQTT client bridge (paho-mqtt), used both:

- as a pure client when the hub phone is active (connects out to its
  Termux-hosted broker), and
- to talk to the locally embedded broker (broker.py) when this PC is the
  fallback hub.

paho-mqtt runs its own background network thread internally (`loop_start()`),
so this class doesn't need to manage threading itself - it just wraps
connect/publish/subscribe with logging and graceful degrade-on-missing-
dependency behaviour, matching broker.py's pattern.
"""

from __future__ import annotations

import logging
from typing import Callable

log = logging.getLogger(__name__)

MESH_TOPIC = "tarno/mesh/events"
HEARTBEAT_TOPIC = "tarno/mesh/heartbeat"


class MqttBridge:
    """Thin wrapper around a paho-mqtt client for the mesh's pub/sub needs."""

    def __init__(self) -> None:
        self._client = None  # paho.mqtt.client.Client
        self._connected = False
        self._on_message: Callable[[str, bytes], None] | None = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self, host: str, port: int = 1883, on_message: Callable[[str, bytes], None] | None = None) -> bool:
        """Connect to a broker at host:port. Returns False (and logs) if
        paho-mqtt isn't installed or the connection fails - never raises,
        matching broker.py's degrade-gracefully approach."""
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            log.warning(
                "paho-mqtt ist nicht installiert - Mesh-MQTT-Verbindung nicht möglich. "
                "`pip install paho-mqtt` nachholen."
            )
            return False

        self._on_message = on_message
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.on_connect = self._handle_connect
        client.on_disconnect = self._handle_disconnect
        client.on_message = self._handle_message

        try:
            client.connect(host, port, keepalive=15)
        except OSError as exc:
            log.info("Mesh-MQTT-Verbindung zu %s:%d fehlgeschlagen: %s", host, port, exc)
            return False

        client.loop_start()
        client.subscribe(MESH_TOPIC)
        client.subscribe(HEARTBEAT_TOPIC)
        self._client = client
        return True

    def disconnect(self) -> None:
        """Stop paho's background network thread and close the connection.
        Safe to call even if connect() was never called or already failed."""
        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
        self._connected = False

    def publish(self, topic: str, payload: str) -> None:
        """Fire-and-forget publish (qos=0) - silently no-ops if not
        connected, logs (never raises) on any client-side failure."""
        if self._client is None:
            return
        try:
            self._client.publish(topic, payload, qos=0)
        except Exception:
            log.debug("Mesh-MQTT-Publish fehlgeschlagen", exc_info=True)

    def _handle_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        self._connected = reason_code == 0
        if self._connected:
            log.info("Mesh-MQTT verbunden")
        else:
            log.warning("Mesh-MQTT-Verbindung abgelehnt: %s", reason_code)

    def _handle_disconnect(self, client, userdata, flags, reason_code, properties=None) -> None:
        self._connected = False
        log.info("Mesh-MQTT getrennt: %s", reason_code)

    def _handle_message(self, client, userdata, message) -> None:
        if self._on_message is not None:
            try:
                self._on_message(message.topic, message.payload)
            except Exception:
                log.exception("Mesh-MQTT: on_message-Callback fehlgeschlagen")
