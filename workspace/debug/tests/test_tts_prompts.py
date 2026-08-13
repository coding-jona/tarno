"""Tests for the TTS-friendly system prompt additions."""

from __future__ import annotations

import unittest

from tarno.ai.conversation import ConversationManager
from tarno.ai.prompts import build_system_prompt
from tarno.ai.prompts.tts_voice_prompt import build_tts_prompt
from tarno.core.config import AudioConfig, TTSPromptConfig, TarnoConfig


class TTSPromptConfigTests(unittest.TestCase):
    def test_audio_config_has_default_tts_prompt(self) -> None:
        cfg = AudioConfig()
        self.assertIsInstance(cfg.tts_prompt, TTSPromptConfig)
        self.assertTrue(cfg.tts_prompt.enabled)
        self.assertEqual(cfg.tts_prompt.voice_hint, "thorsten")

    def test_default_yaml_loads_tts_prompt(self) -> None:
        cfg = TarnoConfig.load()
        self.assertIsInstance(cfg.audio.tts_prompt, TTSPromptConfig)
        self.assertTrue(cfg.audio.tts_prompt.enabled)
        self.assertIn("äh", cfg.audio.tts_prompt.filler_words)


class BuildTTSPromptTests(unittest.TestCase):
    def test_disabled_returns_empty(self) -> None:
        cfg = TTSPromptConfig(enabled=False)
        self.assertEqual(build_tts_prompt(cfg), "")

    def test_contains_voice_hint_and_rules(self) -> None:
        cfg = TTSPromptConfig()
        prompt = build_tts_prompt(cfg)
        self.assertIn("Thorsten", prompt)
        self.assertIn("gesprochenes Deutsch", prompt)
        self.assertIn("Ausrufezeichen", prompt)
        self.assertIn("Kein Markdown", prompt)

    def test_max_sentence_words_is_injected(self) -> None:
        cfg = TTSPromptConfig(max_sentence_words=10)
        prompt = build_tts_prompt(cfg)
        self.assertIn("10 Wörter", prompt)


class BuildSystemPromptTests(unittest.TestCase):
    def test_chat_mode_appends_tts_prompt(self) -> None:
        cfg = TTSPromptConfig()
        prompt = build_system_prompt("chat", tts_config=cfg)
        self.assertIn("Thorsten", prompt)
        self.assertIn("keine Aufzählungslisten", prompt)

    def test_code_mode_ignores_tts_prompt(self) -> None:
        cfg = TTSPromptConfig()
        prompt = build_system_prompt("code", tts_config=cfg)
        self.assertNotIn("Thorsten", prompt)
        self.assertNotIn("gesprochenes Deutsch", prompt)

    def test_chat_mode_without_tts_config_is_unchanged(self) -> None:
        prompt = build_system_prompt("chat")
        self.assertNotIn("Thorsten", prompt)


class ConversationManagerTTSTests(unittest.TestCase):
    def test_chat_system_prompt_contains_tts_rules(self) -> None:
        tts = TTSPromptConfig()
        cm = ConversationManager(tts_config=tts)
        self.assertIn("Thorsten", cm.system_prompt)
        self.assertIn("gesprochenes Deutsch", cm.system_prompt)

    def test_disabled_tts_prompt_not_included(self) -> None:
        tts = TTSPromptConfig(enabled=False)
        cm = ConversationManager(tts_config=tts)
        self.assertNotIn("Thorsten", cm.system_prompt)


if __name__ == "__main__":
    unittest.main()
