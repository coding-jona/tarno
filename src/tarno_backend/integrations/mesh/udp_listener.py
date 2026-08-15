"""UDP broadcast listener for mesh telemetry.

Serves both Node A (secondary phone, Tasker/MacroDroid UDP broadcast) and
Node B (ESP32-S3 scanner, also broadcasting) - both senders use the same transport
and port, so one listener covers both without any per-sender configuration
on the sending side (matches the spec's "dynamic, no hub-IP wiring" goal).

Runs as a plain ``threading.Thread`` with a blocking socket, matching the
rest of the codebase's threading style (see ``proactive_engine.py``) rather
than introducing asyncio.
"""

from __future__ import annotations

import logging
import socket
import threading
from typing import Callable

from tarno_backend.integrations.mesh.payload import MeshEvent

log = logging.getLogger(__name__)

_RECV_BUFFER_SIZE = 8192
_SOCKET_TIMEOUT_SECONDS = 1.0  # bounds how long stop() may have to wait


class UdpBroadcastListener:
    """Listens for UDP broadcast datagrams and hands parsed MeshEvents to a callback."""

    def __init__(self, port: int, on_event: Callable[[MeshEvent], None]) -> None:
        self._port = port
        self._on_event = on_event
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Bind the broadcast socket and spawn the receive thread. A no-op
        if already running; logs (rather than raises) if the port can't be
        bound, matching this integration's "disabled/degraded is fine,
        never crash the app" contract."""
        if self._running:
            return
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(_SOCKET_TIMEOUT_SECONDS)
            sock.bind(("", self._port))
        except OSError:
            log.exception("Mesh-UDP-Listener konnte Port %d nicht binden", self._port)
            return

        self._socket = sock
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="MeshUdpListener")
        self._thread.start()
        log.info("Mesh-UDP-Listener gestartet auf Port %d", self._port)

    def stop(self) -> None:
        """Signal the receive thread to exit, wait briefly for it, then
        close the socket. Safe to call even if start() was never called."""
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None
        log.info("Mesh-UDP-Listener gestoppt")

    def _run(self) -> None:
        """Receive-loop body, run on the background thread started by
        start(). Exits cleanly on stop() or a real socket error; a receive
        timeout is expected/normal (it's just how we periodically re-check
        _running without blocking forever)."""
        assert self._socket is not None
        while self._running and not self._stop_event.is_set():
            try:
                data, addr = self._socket.recvfrom(_RECV_BUFFER_SIZE)
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    log.exception("Mesh-UDP-Listener: Empfangsfehler")
                break

            event = MeshEvent.from_json(data)
            if event is None:
                continue

            try:
                self._on_event(event)
            except Exception:
                log.exception(
                    "Mesh-UDP-Listener: Callback-Fehler für Paket von %s (%s)",
                    addr, event.sender_node,
                )
