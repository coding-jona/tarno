"""Secrets vault abstraction for API keys and tokens."""

from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from tarno.core.exceptions import ConfigError

try:
    from cryptography.fernet import Fernet
except ImportError:  # pragma: no cover
    Fernet = None  # type: ignore[misc, assignment]

try:
    import keyring
    # keyring.get_keyring() normally auto-discovers backends via
    # importlib.metadata entry points. PyInstaller-frozen builds don't
    # preserve that package metadata, so auto-discovery silently falls
    # back to a non-persistent backend and every set()/get() fails quietly
    # (swallowed by the try/except below). Select the Windows backend
    # explicitly so it works identically in dev and in the packaged exe.
    from keyring.backends.Windows import WinVaultKeyring

    keyring.set_keyring(WinVaultKeyring())
except ImportError:  # pragma: no cover
    keyring = None  # type: ignore[assignment]

log = logging.getLogger(__name__)


class SecretStorage(Protocol):
    """Protocol for a secrets backend."""

    def get(self, name: str) -> str | None:
        ...

    def set(self, name: str, value: str) -> None:
        ...


@dataclass
class _EnvStorage:
    """Fallback storage that reads from environment variables."""

    def get(self, name: str) -> str | None:
        env_name = name.upper().replace("-", "_")
        return os.environ.get(env_name) or os.environ.get(name)

    def set(self, name: str, value: str) -> None:
        raise RuntimeError("EnvStorage does not support writing secrets.")


@dataclass
class _KeyringStorage:
    """OS keyring backend via the optional `keyring` package."""

    service: str = "tarno"

    def get(self, name: str) -> str | None:
        if keyring is None:
            log.warning("keyring package not installed; cannot retrieve %s", name)
            return None
        try:
            return keyring.get_password(self.service, name)
        except Exception:
            log.exception("Failed to read secret %s from keyring", name)
            return None

    def set(self, name: str, value: str) -> None:
        if keyring is None:
            raise RuntimeError("keyring package not installed")
        keyring.set_password(self.service, name, value)


@dataclass
class _EncryptedFileStorage:
    """Encrypted JSON file storage using Fernet (requires `cryptography`).

    KERNFIX (Code-Review): der Schluessel wurde vorher per rohem SHA256(master)
    ohne Salt abgeleitet - SHA256 ist absichtlich SCHNELL, also fuer eine
    Passwort-KDF denkbar ungeeignet (ein Angreifer mit der exfiltrierten
    secrets.enc-Datei koennte TARNO_MASTER_KEY mit Milliarden Versuchen/s auf
    einer GPU durchprobieren), und ohne Salt haetten zwei Installationen mit
    demselben Master-Passwort denselben Schluessel gehabt. Jetzt PBKDF2-HMAC-
    SHA256 mit 480.000 Iterationen (OWASP-2023-Empfehlung fuer PBKDF2-SHA256)
    und einem zufaelligen 16-Byte-Salt, das den ersten 16 Bytes der Datei
    vorangestellt wird (kein Geheimnis, nur damit _derive_key() beim Laden
    denselben Schluessel reproduzieren kann).

    Rueckwaertskompatibel: eine bestehende, mit dem ALTEN Schema erzeugte
    Datei hat kein Salt-Praefix - _load() erkennt das (Entschluesselung mit
    dem neuen Schema schlaegt fehl) und faellt einmalig auf die alte
    Ableitung zurueck, schreibt die Datei danach aber sofort im neuen Format
    neu (stille Ein-mal-Migration beim naechsten Zugriff)."""

    path: Path
    _key: bytes | None = None
    _salt: bytes | None = None

    # Laenge des Salt-Praefix in der Datei, siehe Klassendoc oben.
    _SALT_LEN = 16
    _PBKDF2_ITERATIONS = 480_000

    def __post_init__(self) -> None:
        if Fernet is None:
            raise RuntimeError("cryptography package is required for encrypted file storage")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _master_password(self) -> str:
        master = os.environ.get("TARNO_MASTER_KEY")
        if not master:
            raise RuntimeError("TARNO_MASTER_KEY environment variable is required for encrypted file storage")
        return master

    def _derive_key(self, salt: bytes) -> bytes:
        # PBKDF2 mit 480k Iterationen ist ABSICHTLICH langsam (typisch
        # 100-300ms) - ohne Cache wuerde jeder einzelne get()/set()-Aufruf
        # diese Kosten erneut zahlen. Da salt sich nur bei _save() aendert
        # (neues Zufalls-Salt pro Schreibvorgang), reicht ein simpler
        # Ein-Eintrag-Cache pro Instanz.
        if self._salt == salt and self._key is not None:
            return self._key
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=self._PBKDF2_ITERATIONS)
        key = base64.urlsafe_b64encode(kdf.derive(self._master_password().encode("utf-8")))
        self._salt = salt
        self._key = key
        return key

    def _derive_legacy_key(self) -> bytes:
        # Nur fuer die einmalige Migration einer VOR diesem Fix erzeugten
        # Datei - danach nie wieder verwendet (siehe Klassendoc).
        import hashlib
        digest = hashlib.sha256(self._master_password().encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        raw = self.path.read_bytes()
        if not raw:
            return {}

        if len(raw) > self._SALT_LEN:
            salt, encrypted = raw[: self._SALT_LEN], raw[self._SALT_LEN :]
            try:
                fernet = Fernet(self._derive_key(salt))
                data = fernet.decrypt(encrypted)
                return json.loads(data.decode("utf-8"))
            except Exception:
                pass  # evtl. eine Alt-Datei ohne Salt-Praefix - unten versuchen.

        try:
            fernet = Fernet(self._derive_legacy_key())
            data = fernet.decrypt(raw)
            secrets = json.loads(data.decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Could not decrypt secrets file: {exc}") from exc

        log.info("secrets.enc im alten, ungesalzenen Format erkannt - migriere jetzt auf PBKDF2+Salt")
        self._save(secrets)
        return secrets

    def _save(self, secrets: dict[str, str]) -> None:
        import os as _os

        salt = _os.urandom(self._SALT_LEN)
        fernet = Fernet(self._derive_key(salt))
        payload = json.dumps(secrets, ensure_ascii=False).encode("utf-8")
        encrypted = fernet.encrypt(payload)
        self.path.write_bytes(salt + encrypted)

    def get(self, name: str) -> str | None:
        return self._load().get(name)

    def set(self, name: str, value: str) -> None:
        secrets = self._load()
        secrets[name] = value
        self._save(secrets)


class SecretsVault:
    """Unified secrets access with configurable backend.

    Backends:
        - "keyring": OS keyring (recommended on desktop).
        - "encrypted_file": AES-encrypted JSON file (requires TARNO_MASTER_KEY).
        - "env": environment variables (read-only fallback).
    """

    def __init__(self, backend: str = "keyring", path: Path | str | None = None) -> None:
        self._backend_name = backend
        self._backend = self._create_backend(backend, path)

    @staticmethod
    def _create_backend(backend: str, path: Path | str | None) -> SecretStorage:
        if backend == "keyring":
            return _KeyringStorage()
        if backend == "encrypted_file":
            file_path = Path(path) if path else Path.home() / ".tarno" / "secrets.enc"
            return _EncryptedFileStorage(path=file_path)
        if backend == "env":
            return _EnvStorage()
        raise ConfigError(f"Unknown secrets backend: {backend}")

    def get(self, name: str, fallback: str | None = None) -> str | None:
        try:
            value = self._backend.get(name)
        except Exception:
            # A broken backend (e.g. encrypted_file with a wrong/missing
            # TARNO_MASTER_KEY) must not crash every caller that resolves a
            # secret - fall through to the env var / fallback like a normal
            # "not found" instead of propagating a raw exception.
            log.exception("Secrets-Backend '%s' konnte '%s' nicht lesen", self._backend_name, name)
            value = None
        if value:
            return value
        # Always allow an explicit env fallback regardless of backend.
        env_value = os.environ.get(name.upper().replace("-", "_"))
        if env_value:
            return env_value
        return fallback

    def set(self, name: str, value: str) -> None:
        self._backend.set(name, value)
