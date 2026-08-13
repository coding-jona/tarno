"""Encryption at rest helpers for sensitive TARNO data."""

from __future__ import annotations

import base64
import hashlib
import logging
from pathlib import Path
from typing import Any

try:
    from cryptography.fernet import Fernet
except ImportError:  # pragma: no cover
    Fernet = None  # type: ignore[misc, assignment]

log = logging.getLogger(__name__)


class DataEncryption:
    """AES-128-GCM via Fernet for files and byte payloads.

    The key is derived from a master secret using SHA-256. For production
    deployments the master secret should be provided by a secure key manager,
    not hard-coded.
    """

    def __init__(self, master_key: str) -> None:
        if Fernet is None:
            raise RuntimeError("cryptography package is required for encryption")
        self._key = self._derive_key(master_key)
        self._fernet = Fernet(self._key)

    @staticmethod
    def _derive_key(master_key: str) -> bytes:
        digest = hashlib.sha256(master_key.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    def encrypt(self, plaintext: str | bytes) -> bytes:
        if isinstance(plaintext, str):
            plaintext = plaintext.encode("utf-8")
        return self._fernet.encrypt(plaintext)

    def decrypt(self, ciphertext: bytes) -> str:
        data = self._fernet.decrypt(ciphertext)
        return data.decode("utf-8")

    def encrypt_file(self, source: Path | str, target: Path | str) -> None:
        source_path = Path(source)
        target_path = Path(target)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        plaintext = source_path.read_bytes()
        encrypted = self._fernet.encrypt(plaintext)
        target_path.write_bytes(encrypted)

    def decrypt_file(self, source: Path | str, target: Path | str) -> None:
        source_path = Path(source)
        target_path = Path(target)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        ciphertext = source_path.read_bytes()
        plaintext = self._fernet.decrypt(ciphertext)
        target_path.write_bytes(plaintext)

    def rotate_key(
        self,
        old_master_key: str,
        encrypted_payload: bytes,
    ) -> bytes:
        """Re-encrypt a payload with the current key after decrypting with an old key."""
        old = DataEncryption(old_master_key)
        plaintext = old._fernet.decrypt(encrypted_payload)
        return self._fernet.encrypt(plaintext)


def encrypt_sensitive_value(value: Any, master_key: str) -> bytes:
    """Convenience function to encrypt a single value."""
    enc = DataEncryption(master_key)
    return enc.encrypt(str(value))
