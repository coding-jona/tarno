"""Embedded local MQTT broker, used only while this PC is acting as the
mesh's fallback hub (router.py's PC_FALLBACK scenario).

Uses `amqtt` (pure-Python, pip-installable, no Windows service/admin rights
needed) rather than installing Mosquitto as a Windows service - the latter
requires elevation to register, which would block automated setup. Runs its
own asyncio event loop inside a dedicated thread, kept fully isolated from
the rest of the codebase's synchronous/threading style (see udp_listener.py,
heartbeat.py) so it doesn't force asyncio patterns onto anything else.
"""

from __future__ import annotations

import asyncio
import logging
import threading

log = logging.getLogger(__name__)


class EmbeddedMqttBroker:
    """Wraps an `amqtt.broker.Broker` running in its own thread+event loop."""

    def __init__(self, port: int = 1883, bind_host: str = "0.0.0.0") -> None:
        self._port = port
        self._bind_host = bind_host
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._broker = None  # amqtt.broker.Broker, set once the loop is running
        self._started = threading.Event()
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> bool:
        """Start the broker. Returns False (and logs) if `amqtt` isn't
        installed - a missing optional dependency must never crash the
        mesh plugin, only degrade it (matches PluginManager's missing-
        dependency handling, which already logs and continues)."""
        if self._running:
            return True
        try:
            import amqtt  # noqa: F401  (import-check only, used inside the thread)
        except ImportError:
            log.warning(
                "amqtt ist nicht installiert - lokaler MQTT-Broker (PC-Fallback-Hub) "
                "kann nicht gestartet werden. `pip install amqtt` nachholen."
            )
            return False

        self._started.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="MeshEmbeddedBroker")
        self._thread.start()
        if not self._started.wait(timeout=10.0):
            log.error("Eingebetteter MQTT-Broker ist nicht rechtzeitig gestartet")
            return False
        self._running = True
        log.info("Eingebetteter MQTT-Broker gestartet auf %s:%d", self._bind_host, self._port)
        return True

    def stop(self) -> None:
        """Shut down the broker and its event-loop thread. A no-op if the
        broker was never successfully started (e.g. amqtt missing)."""
        if not self._running or self._loop is None:
            return
        self._running = False
        asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        log.info("Eingebetteter MQTT-Broker gestoppt")

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._start_broker())
            self._started.set()
            self._loop.run_forever()
        except Exception:
            log.exception("Eingebetteter MQTT-Broker abgestürzt")
            self._started.set()  # unblock start() even on failure
        finally:
            self._loop.close()

    async def _start_broker(self) -> None:
        from amqtt.broker import Broker

        config = {
            "listeners": {
                "default": {"type": "tcp", "bind": f"{self._bind_host}:{self._port}"},
            },
            "sys_interval": 0,
            "auth": {"allow-anonymous": True},
        }
        self._broker = Broker(config)
        await self._broker.start()

    async def _shutdown(self) -> None:
        if self._broker is not None:
            await self._broker.shutdown()
        assert self._loop is not None
        self._loop.call_soon_threadsafe(self._loop.stop)
