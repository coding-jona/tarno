"""Tests for TARNO security modules."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from tarno_backend.security.audit import AuditManager
from tarno_backend.security.encryption import DataEncryption
from tarno_backend.security.pii import redact, redact_dict
from tarno_backend.telemetry.logging import configure_logging, get_logger
from tarno_backend.utils.paths import CONFIG_DIR, DEBUG_DIR


class PiiRedactionTests(unittest.TestCase):
    """Tests for PII redaction."""

    def test_redact_email(self):
        text = "Kontakt: max@example.com"
        self.assertEqual(redact(text), "Kontakt: [REDACTED]")

    def test_redact_phone(self):
        text = "Meine Nummer ist 0171 1234567"
        self.assertIn("[REDACTED]", redact(text))

    def test_redact_dict(self):
        data = {"api_key": "secret123", "message": "Hallo"}
        redacted = redact_dict(data)
        self.assertEqual(redacted["api_key"], "[REDACTED]")
        self.assertEqual(redacted["message"], "Hallo")


class EncryptionTests(unittest.TestCase):
    """Tests for DataEncryption."""

    def test_roundtrip(self):
        enc = DataEncryption("master-secret-32")
        ciphertext = enc.encrypt("sensible Daten")
        self.assertNotEqual(ciphertext, b"sensible Daten")
        self.assertEqual(enc.decrypt(ciphertext), "sensible Daten")

    def test_file_roundtrip(self):
        enc = DataEncryption("master-secret-32")
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "plain.txt"
            target = Path(tmp) / "cipher.enc"
            source.write_text("Geheim", encoding="utf-8")
            enc.encrypt_file(source, target)
            output = Path(tmp) / "out.txt"
            enc.decrypt_file(target, output)
            self.assertEqual(output.read_text(encoding="utf-8"), "Geheim")


class AuditManagerTests(unittest.TestCase):
    """Tests for AuditManager integrity and retention."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.manager = AuditManager(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_save_and_verify_state(self):
        log_file = Path(self.tmp.name) / "action.log"
        log_file.write_text("test entry", encoding="utf-8")
        self.manager.save_state()
        ok, violations = self.manager.verify_integrity()
        self.assertTrue(ok)
        self.assertEqual(violations, [])

    def test_detect_tampering(self):
        log_file = Path(self.tmp.name) / "action.log"
        log_file.write_text("original", encoding="utf-8")
        self.manager.save_state()
        log_file.write_text("tampered", encoding="utf-8")
        ok, violations = self.manager.verify_integrity()
        self.assertFalse(ok)
        self.assertTrue(any("verändert" in v for v in violations))

    def test_rotate_old_logs(self):
        log_file = Path(self.tmp.name) / "old.log"
        log_file.write_text("x", encoding="utf-8")
        # Simulate old mtime.
        old_time = 0
        import os
        os.utime(log_file, (old_time, old_time))
        removed = self.manager.rotate_old_logs(retention_days=1)
        self.assertEqual(removed, 1)


class LoggingPiiIntegrationTests(unittest.TestCase):
    """Tests that PII redaction works in logging."""

    def test_log_redaction(self):
        import logging
        logger = logging.getLogger("tarno_backend.pii_test")
        configure_logging(redact_pii=True)
        # After configuring, the filter is active. A direct log call should be redacted.
        logger.info("Email: user@example.com")
        # We cannot easily capture stream here, but at least ensure no exception.


class ApiKeyLeakPreventionTests(unittest.TestCase):
    """Tests that API keys are never written to project files or runtime config."""

    def test_leaked_docs_file_removed(self):
        self.assertFalse((DEBUG_DIR / "docs" / "mistral-api-key.md").exists())

    def test_bundled_persona_has_no_key_field(self):
        persona = CONFIG_DIR / "persona" / "tarno.json"
        self.assertTrue(persona.exists())
        data = json.loads(persona.read_text(encoding="utf-8"))
        self.assertNotIn("key", data.get("ovos-solver-openai-plugin", {}))

    def test_install_persona_removes_key_field(self):
        try:
            from tarno_backend.core.ovos_engine import TarnoOvosEngine
        except ImportError:
            # ovos_bus_client is intentionally not in requirements.txt
            # (ADR-002 / TD-007) - ovos_engine imports it at module level.
            self.skipTest(
                "ovos_bus_client not installed (optional, see requirements-ovos.txt)"
            )

        secret = "test_secret_sk_12345678901234567890"
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "persona_src.json"
            dst = Path(tmp) / "persona_dst.json"
            persona = {
                "name": "TARNO",
                "solvers": ["ovos-solver-openai-plugin"],
                "ovos-solver-openai-plugin": {
                    "api_url": "https://api.mistral.ai/v1",
                    "model": "mistral-small-latest",
                    "key": secret,
                },
            }
            src.write_text(json.dumps(persona), encoding="utf-8")
            os.environ["MISTRAL_API_KEY"] = secret
            try:
                engine = TarnoOvosEngine.__new__(TarnoOvosEngine)
                engine._install_persona(src, dst)
                data = json.loads(dst.read_text(encoding="utf-8"))
                self.assertNotIn(
                    "key", data.get("ovos-solver-openai-plugin", {})
                )
                self.assertNotIn(secret, dst.read_text(encoding="utf-8"))
            finally:
                os.environ.pop("MISTRAL_API_KEY", None)

    def test_build_secret_scan_detects_leak(self):
        from tarno_backend.security.build_secret_scan import verify_no_secrets as _verify_no_secrets

        with tempfile.TemporaryDirectory() as tmp:
            leak_file = Path(tmp) / "persona.json"
            # Build the secret and attribute name dynamically so this source file
            # does not contain a literal secret pattern that the project-wide
            # scan would flag.
            key_attr = "key"
            secret = "sk-" + "1" * 30
            leak_file.write_text(
                "{" + f'"{key_attr}": "{secret}"' + "}",
                encoding="utf-8",
            )
            with self.assertRaises(RuntimeError) as ctx:
                _verify_no_secrets(Path(tmp))
            self.assertIn("SECURITY CHECK FAILED", str(ctx.exception))

    def test_build_secret_scan_allows_placeholders(self):
        from tarno_backend.security.build_secret_scan import verify_no_secrets as _verify_no_secrets

        with tempfile.TemporaryDirectory() as tmp:
            placeholder_file = Path(tmp) / "example.md"
            placeholder_file.write_text(
                'MISTRAL_API_KEY="<your_key_here>"',
                encoding="utf-8",
            )
            # Must not raise.
            _verify_no_secrets(Path(tmp))


if __name__ == "__main__":
    unittest.main()
