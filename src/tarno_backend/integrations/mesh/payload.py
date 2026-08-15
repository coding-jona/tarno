"""Universal mesh event payload - the wire format shared by all four nodes
(secondary phone, ESP32-S3 scanner, hub phone, this PC) regardless of which
node is currently acting as hub.

Schema (from the original spec)::

    {
      "sender_node": "SECONDARY_PHONE",
      "target_hub": "DYNAMIC_BROADCAST",
      "timestamp": 1718000000,
      "event_type": "USER_STATE_CHANGE",
      "payload": {
        "screen_state": "ON",
        "battery_level": 78,
        "current_wifi_bssid": "AA:BB:CC:DD:EE:FF",
        "rssi": -55
      }
    }
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class MeshEvent:
    """One parsed telemetry/state message from a mesh node."""

    sender_node: str = ""
    target_hub: str = "DYNAMIC_BROADCAST"
    timestamp: float = 0.0
    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize back to the wire format described in this module's docstring."""
        return json.dumps(
            {
                "sender_node": self.sender_node,
                "target_hub": self.target_hub,
                "timestamp": self.timestamp,
                "event_type": self.event_type,
                "payload": self.payload,
            }
        )

    @classmethod
    def from_json(cls, raw: bytes | str) -> MeshEvent | None:
        """Parse a raw datagram/message. Returns None (and logs) on any
        malformed input - callers must never let a bad packet crash their
        listener loop, matching the ProactiveObserver "never raise for
        expected conditions" philosophy used elsewhere in TARNO."""
        try:
            text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            data = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            log.debug("Mesh-Paket verworfen (kein gültiges JSON): %s", exc)
            return None

        if not isinstance(data, dict):
            log.debug("Mesh-Paket verworfen (kein JSON-Objekt)")
            return None

        sender_node = data.get("sender_node")
        event_type = data.get("event_type")
        if not isinstance(sender_node, str) or not sender_node:
            log.debug("Mesh-Paket verworfen (sender_node fehlt)")
            return None
        if not isinstance(event_type, str) or not event_type:
            log.debug("Mesh-Paket verworfen (event_type fehlt)")
            return None

        payload = data.get("payload")
        if not isinstance(payload, dict):
            payload = {}

        timestamp = data.get("timestamp")
        if not isinstance(timestamp, (int, float)):
            timestamp = time.time()

        target_hub = data.get("target_hub")
        if not isinstance(target_hub, str) or not target_hub:
            target_hub = "DYNAMIC_BROADCAST"

        return cls(
            sender_node=sender_node,
            target_hub=target_hub,
            timestamp=float(timestamp),
            event_type=event_type,
            payload=payload,
        )
