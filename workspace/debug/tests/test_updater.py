"""Tests for the TARNO auto-updater."""

from __future__ import annotations

import hashlib
import unittest
from unittest import mock

from tarno_backend.updater import AutoUpdater, UpdateInfo


class AutoUpdaterTests(unittest.TestCase):
    """Tests for AutoUpdater version comparison and release parsing."""

    def test_newer_version_detected(self):
        updater = AutoUpdater("0.1.0", "owner/repo")
        release = {
            "tag_name": "v0.2.0",
            "body": "Bug fixes",
            "assets": [
                {"name": "tarno_windows_0.2.0.exe", "browser_download_url": "http://example.com/update.exe"},
                {"name": "checksums.txt", "browser_download_url": "http://example.com/checksums.txt"},
            ],
        }
        with mock.patch.object(updater, "_fetch_latest_release", return_value=release):
            info = updater.check()
        self.assertIsNotNone(info)
        self.assertEqual(info.version, "0.2.0")
        self.assertEqual(info.checksum_url, "http://example.com/checksums.txt")

    def test_same_version_returns_none(self):
        updater = AutoUpdater("0.2.0", "owner/repo")
        release = {
            "tag_name": "v0.2.0",
            "body": "",
            "assets": [
                {"name": "tarno_windows_0.2.0.exe", "browser_download_url": "http://example.com/update.exe"},
                {"name": "checksums.txt", "browser_download_url": "http://example.com/checksums.txt"},
            ],
        }
        with mock.patch.object(updater, "_fetch_latest_release", return_value=release):
            info = updater.check()
        self.assertIsNone(info)

    def test_stage_update_writes_file(self):
        import tempfile

        updater = AutoUpdater("0.1.0", "owner/repo")
        checksum_url = "http://example.com/checksums.txt"
        update = UpdateInfo(
            version="0.2.0",
            url="http://example.com/update.exe",
            changelog="",
            checksum_url=checksum_url,
        )
        expected_checksum = hashlib.sha256(b"fake").hexdigest()
        checksum_text = f"{expected_checksum}  update.exe\n"
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("tarno_backend.updater.requests.get") as mock_get:

                def _side_effect(url, **kwargs):
                    response = mock.Mock()
                    response.raise_for_status = lambda: None
                    if url == checksum_url:
                        response.iter_content = lambda chunk_size: [checksum_text.encode()]
                        response.text = checksum_text
                    else:
                        response.iter_content = lambda chunk_size: [b"fake"]
                    response.__enter__ = mock.Mock(return_value=response)
                    response.__exit__ = mock.Mock(return_value=False)
                    return response

                mock_get.side_effect = _side_effect
                path = updater.stage_update(update, staging_dir=tmp)
            self.assertIsNotNone(path)
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
