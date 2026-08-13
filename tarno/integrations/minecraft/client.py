"""Client for the Minecraft Simple Voice Chat companion mod."""

from __future__ import annotations

import json
import logging
import socket
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class MinecraftVoiceConfig:
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 19999


class MinecraftVoiceModule:
    """Controls a client-side Minecraft Simple Voice Chat mod via local TCP.

    The companion mod is expected to run a minimal line-delimited JSON server.
    """

    def __init__(self, config: MinecraftVoiceConfig | None = None) -> None:
        self._config = config or MinecraftVoiceConfig()
        self._socket: socket.socket | None = None

    def connect(self) -> bool:
        if not self._config.enabled:
            return False
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(2.0)
            self._socket.connect((self._config.host, self._config.port))
            log.info("Mit Minecraft Voice Mod verbunden: %s:%d", self._config.host, self._config.port)
            return True
        except Exception as exc:
            log.warning("Minecraft Voice Mod nicht erreichbar: %s", exc)
            if self._socket is not None:
                try:
                    self._socket.close()
                except Exception:
                    pass
            self._socket = None
            return False

    def disconnect(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    def push_to_talk(self, active: bool) -> bool:
        action = "ptt_on" if active else "ptt_off"
        return self._send({"action": action})

    def set_microphone_enabled(self, enabled: bool) -> bool:
        action = "mic_on" if enabled else "mic_off"
        return self._send({"action": action})

    def _send(self, payload: dict[str, Any]) -> bool:
        if self._socket is None and not self.connect():
            return False
        if self._socket is None:
            return False
        try:
            data = json.dumps(payload).encode("utf-8") + b"\n"
            self._socket.sendall(data)
            return True
        except Exception as exc:
            log.warning("Fehler beim Senden an Minecraft Mod: %s", exc)
            self._socket = None
            return False
