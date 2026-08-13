"""Tests for TarnoEngine.set_provider (Phase D: Modell-/Provider-Selektor).

TarnoEngine.__init__ is heavy (constructs SpeechSynthesizer, plugins, etc.)
- these tests bypass it via object.__new__, wiring only the attributes
set_provider actually touches (self.config, self.provider), matching the
lightweight-fake-collaborator pattern already used elsewhere in this suite
(see test_engine_processing_stage.py's _make_bare_engine).
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from tarno.core.config import TarnoConfig
from tarno.core.engine import TarnoEngine


def _make_bare_engine() -> TarnoEngine:
    engine = object.__new__(TarnoEngine)
    engine.config = TarnoConfig()
    engine.provider = MagicMock(name="old-provider")
    engine.provider.name = "mistral"
    return engine


class SetProviderTests(unittest.TestCase):
    def test_switch_to_ollama_succeeds_without_api_key(self) -> None:
        """Ollama needs no API key (not in _PROVIDER_SECRET_NAMES) - must
        succeed and actually swap the live provider object."""
        engine = _make_bare_engine()

        success, message = engine.set_provider("ollama")

        self.assertTrue(success)
        self.assertEqual(engine.provider.name, "ollama")

    def test_unknown_provider_fails_without_touching_active_provider(self) -> None:
        """Most critical case: a failed switch must have NO side effect -
        the previously active provider object must remain untouched."""
        engine = _make_bare_engine()
        original_provider = engine.provider

        success, message = engine.set_provider("does_not_exist")

        self.assertFalse(success)
        self.assertIs(engine.provider, original_provider)
        self.assertEqual(engine.provider.name, "mistral")

    def test_missing_api_key_fails_without_any_network_attempt(self) -> None:
        """Providers that need a key (mistral) must be rejected by the
        pre-check BEFORE create_provider (and therefore any real API call)
        is ever invoked, verified via a mock call-count of zero."""
        engine = _make_bare_engine()
        original_provider = engine.provider

        with patch("tarno.security.secrets.SecretsVault.get", return_value=None), \
             patch("tarno.ai.factory.create_provider") as mock_create:
            success, message = engine.set_provider("mistral")

        self.assertFalse(success)
        self.assertIn("API-Key", message)
        mock_create.assert_not_called()
        self.assertIs(engine.provider, original_provider)

    def test_claude_legacy_env_var_alias_is_accepted(self) -> None:
        """Regression test: docs/api-keys.md and the legacy first-start
        wizard used to point users at CLAUDE_API_KEY instead of the actually
        checked ANTHROPIC_API_KEY - set_provider("claude") must still
        succeed for a user who set the key under the old (wrong) name."""
        engine = _make_bare_engine()
        fake_new_provider = MagicMock()
        fake_new_provider.name = "claude"

        def fake_get(self, name, fallback=None):
            return "fake-key" if name == "CLAUDE_API_KEY" else None

        with patch("tarno.security.secrets.SecretsVault.get", fake_get), \
             patch("tarno.ai.factory.create_provider", return_value=fake_new_provider) as mock_create:
            success, message = engine.set_provider("claude")

        mock_create.assert_called_once()
        self.assertTrue(success)
        self.assertIs(engine.provider, fake_new_provider)

    def test_present_api_key_allows_switch_attempt(self) -> None:
        """With a key configured, the pre-check passes and create_provider
        is actually invoked (its result is what gets swapped in)."""
        engine = _make_bare_engine()
        fake_new_provider = MagicMock()
        fake_new_provider.name = "mistral"

        with patch("tarno.security.secrets.SecretsVault.get", return_value="fake-key"), \
             patch("tarno.ai.factory.create_provider", return_value=fake_new_provider) as mock_create:
            success, message = engine.set_provider("mistral")

        mock_create.assert_called_once()
        self.assertTrue(success)
        self.assertIs(engine.provider, fake_new_provider)


if __name__ == "__main__":
    unittest.main()
