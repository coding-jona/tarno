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

HUB = "HUB"
ESP32 = "ESP32"
SECONDARY = "SECONDARY"
WIKO = "WIKO"


class HeartbeatMonitor:
    """Tracks last-seen timestamps per node and reports online/offline state."""

    def __init__(self, heartbeat_interval_seconds: float = 4.0) -> None:
        self._interval = heartbeat_interval_seconds
        self._timeout = heartbeat_interval_seconds * 3
        self._last_seen: dict[str, float] = {}
        self._lock = threading.Lock()

    def mark_seen(self, node: str) -> None:
        with self._lock:
            self._last_seen[node] = time.monotonic()

    def is_online(self, node: str) -> bool:
        with self._lock:
            last = self._last_seen.get(node)
        if last is None:
            return False
        return (time.monotonic() - last) < self._timeout

    def seconds_since_seen(self, node: str) -> float | None:
        with self._lock:
            last = self._last_seen.get(node)
        if last is None:
            return None
        return time.monotonic() - last

    @property
    def interval_seconds(self) -> float:
        return self._interval
