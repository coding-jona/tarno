"""Tests for the curated per-provider model catalog (Phase 1-6)."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from tarno_backend.ai.model_catalog import PROVIDER_MODEL_CATALOG, ModelInfo
from tarno_backend.ai.ollama_client import list_ollama_models


class ProviderModelCatalogTests(unittest.TestCase):
    def test_all_curated_providers_have_at_least_one_model(self) -> None:
        for provider, models in PROVIDER_MODEL_CATALOG.items():
            with self.subTest(provider=provider):
                self.assertGreater(len(models), 0)

    def test_every_model_has_id_label_and_capabilities(self) -> None:
        for models in PROVIDER_MODEL_CATALOG.values():
            for model in models:
                self.assertIsInstance(model, ModelInfo)
                self.assertTrue(model.id)
                self.assertTrue(model.label)
                self.assertTrue(1 <= len(model.capabilities) <= 3)

    def test_mistral_is_in_the_catalog(self) -> None:
        """Mistral muss im Katalog wählbar sein (Provider-Picker + Agent-Pool)."""
        self.assertIn("mistral", PROVIDER_MODEL_CATALOG)
        self.assertGreater(len(PROVIDER_MODEL_CATALOG["mistral"]), 0)


class ListOllamaModelsTests(unittest.TestCase):
    def test_returns_model_names_from_api_tags(self) -> None:
        fake_response = json.dumps({
            "models": [{"name": "qwen2.5:latest"}, {"name": "jarvis:latest"}]
        }).encode("utf-8")

        class _FakeResp:
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return None
            def read(self):
                return fake_response

        with patch("urllib.request.urlopen", return_value=_FakeResp()):
            models = list_ollama_models()

        self.assertEqual(models, ["qwen2.5:latest", "jarvis:latest"])

    def test_unreachable_server_returns_empty_list_not_exception(self) -> None:
        import urllib.error

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("nope")):
            models = list_ollama_models()

        self.assertEqual(models, [])


if __name__ == "__main__":
    unittest.main()
