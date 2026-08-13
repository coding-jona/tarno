"""Phase 2 tests for atomic config writes and corruption recovery."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from tarno_backend.core.config import TarnoConfig, _load_yaml


class AtomicConfigWriteTests(unittest.TestCase):
    """Test that config.save() uses atomic writes."""

    def test_save_creates_file(self):
        """save() must create the config file even if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "config.yaml"
            config = TarnoConfig()
            config.save(path)

            self.assertTrue(path.exists())
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertIsInstance(data, dict)
            self.assertEqual(data.get("language"), "de")

    def test_save_creates_backup(self):
        """save() must create a .bak file when overwriting."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            # Write initial config
            config1 = TarnoConfig(language="de")
            config1.save(path)

            # Overwrite with new config
            config2 = TarnoConfig(language="en")
            config2.save(path)

            backup = path.with_suffix(".yaml.bak")
            self.assertTrue(backup.exists(), "Backup should exist after overwrite")

            # Backup should contain old language
            backup_data = yaml.safe_load(backup.read_text(encoding="utf-8"))
            self.assertEqual(backup_data["language"], "de")

            # Main file should contain new language
            main_data = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(main_data["language"], "en")

    def test_no_temp_files_left_on_success(self):
        """After a successful save, no .tmp files should remain."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            config = TarnoConfig()
            config.save(path)

            tmp_files = list(Path(tmp).glob(".tarno_cfg_*.tmp"))
            self.assertEqual(len(tmp_files), 0, "No temp files should remain")

    def test_save_is_valid_yaml(self):
        """The saved file must be parseable YAML."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            config = TarnoConfig()
            config.save(path)

            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertIsInstance(data, dict)
            self.assertIn("audio", data)
            self.assertIn("wakeword", data)
            self.assertIn("llm", data)


class CorruptionRecoveryTests(unittest.TestCase):
    """Test that _load_yaml falls back to .bak on corruption."""

    def test_load_valid_yaml(self):
        """Normal YAML file should load correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text("language: de\ntheme: dark\n", encoding="utf-8")

            data = _load_yaml(path)
            self.assertEqual(data["language"], "de")

    def test_load_corrupt_yaml_falls_back_to_backup(self):
        """Corrupt YAML should trigger backup loading."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            backup = path.with_suffix(".yaml.bak")

            # Write corrupt main file
            path.write_text("{{{{invalid yaml: [", encoding="utf-8")

            # Write valid backup
            backup.write_text("language: de\ntheme: dark\n", encoding="utf-8")

            data = _load_yaml(path)
            self.assertEqual(data["language"], "de")

    def test_load_empty_yaml_returns_empty_dict(self):
        """Empty YAML file (returns None from safe_load) should fallback."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text("", encoding="utf-8")

            # Empty YAML = None from safe_load → not a dict → try backup
            # No backup exists → return {}
            data = _load_yaml(path)
            self.assertEqual(data, {})

    def test_load_nonexistent_returns_empty(self):
        """Missing file should return empty dict without error."""
        path = Path("/nonexistent/path/config.yaml")
        data = _load_yaml(path)
        self.assertEqual(data, {})

    def test_both_corrupt_returns_empty(self):
        """If both main and backup are corrupt, return empty dict."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            backup = path.with_suffix(".yaml.bak")

            path.write_text("{{corrupt", encoding="utf-8")
            backup.write_text("{{also corrupt", encoding="utf-8")

            data = _load_yaml(path)
            self.assertEqual(data, {})

    def test_yaml_list_treated_as_corrupt(self):
        """A YAML file that parses to a list (not dict) should fallback."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            backup = path.with_suffix(".yaml.bak")

            path.write_text("- item1\n- item2\n", encoding="utf-8")
            backup.write_text("language: en\n", encoding="utf-8")

            data = _load_yaml(path)
            self.assertEqual(data["language"], "en")


class ConfigRoundtripTests(unittest.TestCase):
    """Test that save → load preserves configuration."""

    def test_roundtrip_preserves_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"

            original = TarnoConfig(language="de", theme="dark", log_level="DEBUG")
            original.save(path)

            loaded = TarnoConfig.load(path)
            self.assertEqual(loaded.language, "de")
            self.assertEqual(loaded.theme, "dark")
            self.assertEqual(loaded.log_level, "DEBUG")

    def test_multiple_saves_keep_backups_current(self):
        """Each save should update the backup to the previous version."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            backup = path.with_suffix(".yaml.bak")

            TarnoConfig(language="v1").save(path)
            TarnoConfig(language="v2").save(path)
            TarnoConfig(language="v3").save(path)

            main = yaml.safe_load(path.read_text(encoding="utf-8"))
            bak = yaml.safe_load(backup.read_text(encoding="utf-8"))

            self.assertEqual(main["language"], "v3")
            self.assertEqual(bak["language"], "v2")


if __name__ == "__main__":
    unittest.main()
