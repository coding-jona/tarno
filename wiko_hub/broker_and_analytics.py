"""TARNO Mesh - Wiko View 5 Plus primary hub (runs under Termux).

Standalone script (deliberately self-contained, no `tarno` package import -
Termux won't have the full TARNO backend installed, only Python + a couple
of pip packages). Reimplements the minimal parts of the universal payload
schema it needs (`tarno/integrations/mesh/payload.py` on the PC side is the
canonical version - keep this copy in sync if that schema ever changes).

Responsibilities while Wiko is the active hub (MeshRouter's FULL_MESH
scenario on the PC side):
  1. Runs a local MQTT broker (amqtt) other nodes/the PC can connect to.
  2. Listens for the ZTE phone's direct UDP broadcasts (same transport/port
     as the PC's udp_listener.py, so both can receive Node A's telemetry
     independently - no single point of failure).
  3. Computes simple focus-score/usage-pattern analytics from the telemetry
     stream, offloading that work from the PC per the original spec.
  4. Appends every event to a local JSONL log (`~/tarno_mesh/events.jsonl`)
     - this IS the "sync on boot" mechanism: when the PC comes back online
       and Wiko was hub for a while, it (or the user, initially) can pull
       this file via `adb pull` / Termux file sharing rather than needing a
       live push sync, keeping this v1 deliberately simple per the plan.

Usage (inside Termux):
    python broker_and_analytics.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("wiko_hub")

UDP_PORT = 47800
MQTT_PORT = 1883
LOG_DIR = Path.home() / "tarno_mesh"
LOG_FILE = LOG_DIR / "events.jsonl"


@dataclass
class FocusStats:
    """Very simple focus-score heuristic: fraction of the last window where
    the screen was ON is used as a rough "active usage" proxy. Intentionally
    basic for v1 - the PC-side analytics (once it takes over in PC_FALLBACK)
    doesn't need to replicate this exactly, just provide *some* signal."""

    screen_on_seconds: float = 0.0
    screen_off_seconds: float = 0.0
    last_state: str | None = None
    last_change: float = field(default_factory=time.time)

    def update(self, screen_state: str) -> None:
        now = time.time()
        elapsed = now - self.last_change
        if self.last_state == "ON":
            self.screen_on_seconds += elapsed
        elif self.last_state == "OFF":
            self.screen_off_seconds += elapsed
        self.last_state = screen_state
        self.last_change = now

    @property
    def focus_score(self) -> float:
        total = self.screen_on_seconds + self.screen_off_seconds
        if total <= 0:
            return 0.0
        return round(100.0 * self.screen_on_seconds / total, 1)


def parse_event(raw: bytes) -> dict[str, Any] | None:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or "sender_node" not in data or "event_type" not in data:
        return None
    return data


def append_log(event: dict[str, Any]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def udp_listener(stats: FocusStats) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("", UDP_PORT))
    log.info("UDP-Listener aktiv auf Port %d", UDP_PORT)

    while True:
        data, addr = sock.recvfrom(8192)
        event = parse_event(data)
        if event is None:
            continue
        log.info("Event von %s (%s): %s", event.get("sender_node"), addr[0], event.get("event_type"))
        append_log(event)

        payload = event.get("payload", {})
        if isinstance(payload, dict) and "screen_state" in payload:
            stats.update(payload["screen_state"])
            log.info("Fokus-Score (grob): %.1f%%", stats.focus_score)


async def run_broker() -> None:
    try:
        from amqtt.broker import Broker
    except ImportError:
        log.warning(
            "amqtt nicht installiert - `pip install amqtt` in Termux nachholen. "
            "UDP-Listener/Analytics laufen trotzdem weiter, nur der MQTT-Broker-Teil fehlt."
        )
        return

    config = {
        "listeners": {"default": {"type": "tcp", "bind": f"0.0.0.0:{MQTT_PORT}"}},
        "sys_interval": 0,
        "auth": {"allow-anonymous": True},
    }
    broker = Broker(config)
    await broker.start()
    log.info("MQTT-Broker aktiv auf Port %d", MQTT_PORT)
    await asyncio.Event().wait()  # run forever


def main() -> None:
    import threading

    stats = FocusStats()
    threading.Thread(target=udp_listener, args=(stats,), daemon=True).start()

    try:
        asyncio.run(run_broker())
    except KeyboardInterrupt:
        log.info("Wiko-Hub beendet.")


if __name__ == "__main__":
    main()
