"""Presence tracking for mesh nodes (Hub-Handy, Zweitgeraet-Handy, ESP32
scanner - geraeteneutrale Rollennamen, kein Marken-/Modellbezug im Code, da
andere Nutzer andere Handymodelle einsetzen als die urspruenglich hier
entwickelten).

A node counts as "online" if it has been seen (heartbeat or any telemetry
packet) within `timeout_seconds` (default: 3x the heartbeat interval, so a
single missed beat doesn't immediately flip state - avoids flapping).
"""

from __future__ import annotations

import logging
import threading
import time

log = logging.getLogger(__name__)

ESP32 = "ESP32"
# WIKO/ZTE are the tests' + default-config's node identifiers - MeshRouter
# tracks presence under whatever hub_node_match/secondary_node_match string
# it's configured with (see router.py), not a fixed pair of role constants,
# so no "HUB"/"SECONDARY" constants are needed here.
WIKO = "WIKO"
ZTE = "ZTE"


class HeartbeatMonitor:
    """Tracks last-seen timestamps per node and reports online/offline state."""

    def __init__(self, heartbeat_interval_seconds: float = 4.0) -> None:
        self._interval = heartbeat_interval_seconds
        self._timeout = heartbeat_interval_seconds * 3
        self._last_seen: dict[str, float] = {}
        self._lock = threading.Lock()

    def mark_seen(self, node: str) -> None:
        """Record that `node` was just heard from (heartbeat or any packet)."""
        with self._lock:
            self._last_seen[node] = time.monotonic()

    def is_online(self, node: str) -> bool:
        """True if `node` was seen within the last 3 heartbeat intervals.
        False for a node that's never been seen at all."""
        with self._lock:
            last = self._last_seen.get(node)
        if last is None:
            return False
        return (time.monotonic() - last) < self._timeout

    def seconds_since_seen(self, node: str) -> float | None:
        """Seconds since `node` was last seen, or None if never seen."""
        with self._lock:
            last = self._last_seen.get(node)
        if last is None:
            return None
        return time.monotonic() - last

    @property
    def interval_seconds(self) -> float:
        return self._interval
