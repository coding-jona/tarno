"""Tests for tarno/ai/pool/edit_apply.py (Agent-Pool Phase 2)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from tarno.ai.pool.edit_apply import apply_merged_instruction
from tarno.ai.pool.models import PoolAgentSpec
from tarno.core.config import TarnoConfig


class ApplyMergedInstructionTests(unittest.TestCase):
    def test_uses_lead_provider_and_model_not_global_config(self) -> None:
        config = TarnoConfig()
        self.assertEqual(config.coding.provider, "mistral")
        self.assertEqual(config.coding.model, "codestral-latest")

        lead = PoolAgentSpec(provider="claude", model="claude-x", role="lead")

        captured_configs = []

        class _FakeBackend:
            def __init__(self, cfg, secrets=None):
                captured_configs.append(cfg)

            def run(self, prompt, workspace, fnames, read_only, on_output=None):
                yield from ()

        with patch("tarno.ai.pool.edit_apply.AiderBackend", _FakeBackend):
            list(apply_merged_instruction(lead, config, "tu etwas", {}, [], False))

        self.assertEqual(len(captured_configs), 1)
        self.assertEqual(captured_configs[0].coding.provider, "claude")
        self.assertEqual(captured_configs[0].coding.model, "claude-x")
        # Original config object must stay untouched (dataclasses.replace, not mutation).
        self.assertEqual(config.coding.provider, "mistral")
        self.assertEqual(config.coding.model, "codestral-latest")


if __name__ == "__main__":
    unittest.main()
