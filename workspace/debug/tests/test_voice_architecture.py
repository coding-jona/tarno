"""Tests for voice permission, audio manager and echo protection."""

from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

import numpy as np

from tarno.core.command_engine import RiskLevel
from tarno.core.exceptions import PermissionDeniedError
from tarno.voice.audio_manager import AudioManager, AudioState, OutputDeviceType
from tarno.voice.echo_protection import EchoProtection
from tarno.voice.permission_manager import (
    VoicePermissionManager,
    VoicePermissionType,
)


class VoicePermissionManagerTests(unittest.TestCase):
    """Tests for VoicePermissionManager."""

    def test_basic_voice_input_auto_granted(self):
        manager = VoicePermissionManager()
        self.assertTrue(
            manager.request(VoicePermissionType.VOICE_INPUT_BASIC, "local_mic")
        )

    def test_recording_requires_confirmation(self):
        manager = VoicePermissionManager(
            dialog_factory=lambda permission, target, risk, duration: (True, False)
        )
        self.assertTrue(
            manager.request(VoicePermissionType.VOICE_RECORDING, "local_recording")
        )

    def test_high_risk_never_persistent(self):
        calls: list[bool] = []

        def dialog(permission, target, risk, duration):
            calls.append(True)
            return True, True  # user tries to make it persistent

        manager = VoicePermissionManager(dialog_factory=dialog)
        manager.request(VoicePermissionType.VOICE_GAME_INTEGRATION, "minecraft")
        # The session grant exists, but it must not be stored persistently.
        self.assertTrue(
            manager.is_granted(VoicePermissionType.VOICE_GAME_INTEGRATION, "minecraft")
        )
        self.assertEqual(len(manager._persistent_grants), 0)

    def test_external_output_denied(self):
        manager = VoicePermissionManager(
            dialog_factory=lambda permission, target, risk, duration: (False, False)
        )
        with self.assertRaises(PermissionDeniedError):
            manager.request(VoicePermissionType.VOICE_EXTERNAL_OUTPUT, "discord")

    def test_persistent_grants_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy = Path(tmp) / "voice_policy.yaml"
            manager = VoicePermissionManager(
                policy_file=policy,
                dialog_factory=lambda p, t, r, d: (True, True),
            )
            manager.request(VoicePermissionType.VOICE_RECORDING, "local_recording")
            self.assertTrue(policy.exists())

            manager2 = VoicePermissionManager(policy_file=policy)
            self.assertTrue(
                manager2.is_granted(VoicePermissionType.VOICE_RECORDING, "local_recording")
            )


class EchoProtectionTests(unittest.TestCase):
    """Tests for EchoProtection."""

    def test_suppressed_during_tts(self):
        echo = EchoProtection()
        echo.on_tts_started()
        self.assertTrue(echo.is_suppressed())

    def test_suppressed_after_tts_cooldown(self):
        echo = EchoProtection()
        echo.on_tts_finished()
        self.assertTrue(echo.is_suppressed())

    def test_energy_heuristic_detects_echo(self):
        echo = EchoProtection()
        echo.on_tts_started()
        # TTS reference energy.
        echo.record_reference_energy(np.full(16000, 5000, dtype=np.int16))
        # Microphone chunk with similar energy -> echo risk.
        mic_chunk = np.full(16000, 4000, dtype=np.int16)
        self.assertTrue(echo.detect_echo_risk(mic_chunk))

    def test_low_energy_is_safe(self):
        echo = EchoProtection()
        echo.on_tts_started()
        echo.record_reference_energy(np.full(16000, 5000, dtype=np.int16))
        mic_chunk = np.full(16000, 10, dtype=np.int16)
        self.assertFalse(echo.detect_echo_risk(mic_chunk))


class AudioManagerTests(unittest.TestCase):
    """Tests for AudioManager routing decisions."""

    def test_headphones_allow_tts(self):
        audio = AudioManager()
        audio._headphones_connected = True
        audio._microphone_open = True
        audio.enter_tts()
        self.assertTrue(audio.should_use_tts())

    def test_speakers_with_mic_block_tts(self):
        audio = AudioManager()
        audio._current_output = OutputDeviceType.SPEAKERS
        audio._microphone_open = True
        self.assertFalse(audio.should_use_tts())

    def test_text_only_blocks_tts(self):
        audio = AudioManager()
        audio._headphones_connected = True
        audio.set_echo_risk(True)
        self.assertFalse(audio.should_use_tts())


if __name__ == "__main__":
    unittest.main()
