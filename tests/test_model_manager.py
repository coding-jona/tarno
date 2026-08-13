"""Tests for the model manager download and verification logic."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tarno.model_manager import ModelInfo, ModelManager


class ModelManagerTests(unittest.TestCase):
    def test_required_models_from_config(self):
        config = [
            {"name": "test-model", "filename": "test.bin", "url": "http://example.com/test.bin"}
        ]
        mgr = ModelManager(models_config=config)
        models = mgr.required_models()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].name, "test-model")

    def test_is_downloaded_checks_sha256(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.bin"
            path.write_bytes(b"hello")
            sha = hashlib.sha256(b"hello").hexdigest()
            mgr = ModelManager(models_dir=tmp)
            model = ModelInfo(name="m", filename="model.bin", url="", sha256=sha)
            self.assertTrue(mgr.is_downloaded(model))

            bad = ModelInfo(name="m", filename="model.bin", url="", sha256="00" * 32)
            self.assertFalse(mgr.is_downloaded(bad))

    def test_download_with_mock_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            mgr = ModelManager(models_dir=tmp)
            model = ModelInfo(name="m", filename="m.bin", url="http://x/m.bin")
            response = mock.MagicMock(
                status_code=200,
                headers={"content-length": "5"},
                iter_content=lambda chunk_size: [b"hello"],
            )
            response.__enter__ = mock.MagicMock(return_value=response)
            response.__exit__ = mock.MagicMock(return_value=False)
            with mock.patch("requests.get", return_value=response) as mock_get:
                with mock.patch.object(
                    mgr, "_sha256_of", return_value="mocksha"
                ):
                    result = mgr.download(model)
            self.assertTrue(result)
            mock_get.assert_called_once()
