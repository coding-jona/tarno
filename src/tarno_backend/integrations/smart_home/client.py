"""Vendor-agnostic smart home device abstraction."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class SmartDevice:
    id: str
    name: str
    room: str
    device_type: str
    state: dict[str, Any]


class SmartHomeBackend(ABC):
    """Abstract backend for smart home platforms (e.g. Home Assistant, openHAB)."""

    @abstractmethod
    def discover(self) -> list[SmartDevice]: ...

    @abstractmethod
    def set_state(self, device_id: str, key: str, value: Any) -> bool: ...

    @abstractmethod
    def is_available(self) -> bool: ...


class HomeAssistantBackend(SmartHomeBackend):
    """Example backend for Home Assistant via REST API.

    Requires a long-lived access token and a base URL.
    """

    def __init__(self, base_url: str, token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def is_available(self) -> bool:
        try:
            import requests
            response = requests.get(f"{self._base_url}/api/", headers=self._headers(), timeout=3)
            return response.status_code == 200
        except Exception:
            return False

    def discover(self) -> list[SmartDevice]:
        import requests
        response = requests.get(
            f"{self._base_url}/api/states",
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        devices: list[SmartDevice] = []
        for item in response.json():
            entity_id = item.get("entity_id", "")
            # Filter simple domains as a demo; real logic would be configurable.
            if "." in entity_id:
                domain, name = entity_id.split(".", 1)
                devices.append(SmartDevice(
                    id=entity_id,
                    name=item.get("attributes", {}).get("friendly_name", name),
                    room=item.get("attributes", {}).get("room", "unknown"),
                    device_type=domain,
                    state={"state": item.get("state")},
                ))
        return devices

    def set_state(self, device_id: str, key: str, value: Any) -> bool:
        # `key` is part of the shared SmartHomeBackend interface but unused
        # here: this demo implementation only supports the basic on/off
        # service call, not arbitrary attribute writes (e.g. brightness).
        import requests
        domain = device_id.split(".")[0]
        service = "turn_on" if value else "turn_off"
        payload = {"entity_id": device_id}
        try:
            response = requests.post(
                f"{self._base_url}/api/services/{domain}/{service}",
                headers=self._headers(),
                json=payload,
                timeout=10,
            )
            return response.status_code < 300
        except Exception:
            return False


class SmartHomeClient:
    """Aggregates smart home backends and exposes a unified interface."""

    def __init__(self, backends: list[SmartHomeBackend] | None = None) -> None:
        self._backends = backends or []

    def add_backend(self, backend: SmartHomeBackend) -> None:
        self._backends.append(backend)

    @property
    def backend_count(self) -> int:
        return len(self._backends)

    def discover(self) -> list[SmartDevice]:
        devices: list[SmartDevice] = []
        for backend in self._backends:
            try:
                devices.extend(backend.discover())
            except Exception:
                log.exception("Smart-Home Discovery fehlgeschlagen")
        return devices

    def set_state(self, device_id: str, key: str, value: Any) -> bool:
        for backend in self._backends:
            if backend.is_available():
                return backend.set_state(device_id, key, value)
        return False
