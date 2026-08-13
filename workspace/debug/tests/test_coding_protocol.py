"""Tests for the coding subsystem protocol and config defaults."""

from __future__ import annotations

import unittest

from tarno_backend.ai.coding.protocol import CodingOutput
from tarno_backend.core.config import TarnoConfig


class CodingProtocolTests(unittest.TestCase):
    def test_coding_output_frozen_dataclass(self) -> None:
        output = CodingOutput(kind="text", text="Hallo")
        self.assertEqual(output.kind, "text")
        self.assertEqual(output.text, "Hallo")

    def test_coding_output_defaults(self) -> None:
        output = CodingOutput(kind="summary", text="Fertig")
        self.assertEqual(output.timestamp_ms, 0)
        self.assertEqual(output.meta, {})

    def test_coding_config_defaults(self) -> None:
        config = TarnoConfig()
        self.assertTrue(config.coding.enabled)
        self.assertEqual(config.coding.provider, "mistral")
        self.assertEqual(config.coding.model, "codestral-latest")
        self.assertEqual(config.coding.backend, "native")
        self.assertFalse(config.coding.read_only_default)
        self.assertEqual(config.coding.timeout, 0.0)
        self.assertFalse(config.coding.auto_allow)
