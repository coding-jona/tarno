"""Read-only client fuer den Tarno-Server (tarno-server FastAPI-Backend,
Strato-VPS/tarno.cousinsmp.de) - GANZ GETRENNT vom lokalen UDP/MQTT-Hybrid-
Mesh (siehe client.py/router.py in diesem Paket). Dieser Client liefert die
NEUE Cloud-Tracking-Daten (Akku, Standort, App-Nutzung pro Handy, Proximity
pro ESP32) fuer den mesh_device_status-Tool-Call - siehe plugin.py.

Auth: kein eigener Login-Flow hier. Die WinUI3-Desktop-App speichert den
Account-Access-Token bereits im Windows Credential Manager (siehe
TARNO.UI/Services/MeshCredentialStore.cs, Resource "TarnoMesh.ServerAccessToken",
WinRT PasswordVault - fuer unpackaged Apps landet das als klassisches
CRED_TYPE_GENERIC im selben Windows-Credential-Store, lesbar per win32cred).
Dieser Client liest denselben Eintrag wieder aus, statt ein zweites,
eigenes Login/Token-Handling aufzubauen - beide laufen ohnehin auf demselben
Windows-Benutzerkonto. Kein Schreibzugriff, keine eigene Passwortabfrage."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests

log = logging.getLogger(__name__)

_CRED_TARGET_NAME = "TarnoMesh.ServerAccessToken"
_REQUEST_TIMEOUT_S = 6.0


@dataclass(frozen=True)
class StoredToken:
    email: str
    access_token: str


def _read_stored_token() -> StoredToken | None:
    """Liest den von der WinUI3-App gespeicherten Access-Token aus dem
    Windows Credential Manager. None, wenn nicht eingeloggt oder win32cred
    nicht verfuegbar (z.B. beim Testen auf Nicht-Windows) - kein Fehler,
    einfach "nicht konfiguriert"."""
    try:
        import win32cred
    except ImportError:
        log.debug("win32cred nicht verfuegbar (kein Windows?) - Mesh-Cloud-Tool bleibt inaktiv.")
        return None

    try:
        cred = win32cred.CredRead(TargetName=_CRED_TARGET_NAME, Type=win32cred.CRED_TYPE_GENERIC)
    except Exception:
        # Normalfall, wenn in der WinUI3-App noch niemand eingeloggt ist -
        # kein echter Fehler, kein Stacktrace-Rauschen im Log.
        return None

    blob = cred.get("CredentialBlob")
    if not blob:
        return None
    token = blob.decode("utf-16-le") if isinstance(blob, (bytes, bytearray)) else str(blob)
    email = cred.get("UserName") or ""
    if not token:
        return None
    return StoredToken(email=email, access_token=token)


def fetch_devices(server_url: str) -> tuple[list[dict[str, Any]] | None, str | None]:
    """GET {server_url}/devices mit dem gespeicherten Account-Token.

    Returns (devices, error_message) - genau eines der beiden ist None.
    devices ist die rohe DeviceOut-Liste des Servers (siehe
    tarno-server/app/schemas.py), inkl. last_payloads pro Geraet."""
    token = _read_stored_token()
    if token is None:
        return None, (
            "Kein gespeicherter Tarno-Mesh-Login gefunden - erst in der TARNO-Desktop-App "
            "auf der Mesh-Geraete-Seite einloggen."
        )

    try:
        response = requests.get(
            f"{server_url.rstrip('/')}/devices",
            headers={"Authorization": f"Bearer {token.access_token}"},
            timeout=_REQUEST_TIMEOUT_S,
        )
    except requests.RequestException as exc:
        return None, f"Tarno-Server nicht erreichbar ({server_url}): {exc}"

    if response.status_code == 401:
        return None, "Gespeicherter Login ist abgelaufen - in der TARNO-Desktop-App neu einloggen."
    if response.status_code >= 400:
        return None, f"Tarno-Server antwortete mit HTTP {response.status_code}."

    try:
        return response.json(), None
    except ValueError:
        return None, "Unerwartete Antwort vom Tarno-Server (kein gueltiges JSON)."
