"""Echo and self-trigger protection for TARNO TTS output."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import numpy as np

log = logging.getLogger(__name__)


@dataclass
class EchoProtectionConfig:
    cooldown_ms: int = 2000
    energy_threshold: float = 0.15
    sample_rate: int = 16000


class EchoProtection:
    """Suppresses wake word processing while TTS is playing and for a cooldown
    afterwards. Also provides a simple energy heuristic to detect echo risk.
    """

    def __init__(self, config: EchoProtectionConfig | None = None) -> None:
        self._config = config or EchoProtectionConfig()
        self._tts_active = False
        self._cooldown_until = 0.0
        self._reference_energy: float = 0.0

    def on_tts_started(self) -> None:
        """Call when TTS playback begins - suppresses wake-word processing
        until on_tts_finished() plus the cooldown window."""
        self._tts_active = True
        log.debug("EchoProtection: TTS gestartet")

    def on_tts_finished(self) -> None:
        """Call when TTS playback ends - starts the post-playback cooldown."""
        self._tts_active = False
        self._cooldown_until = time.monotonic() + (self._config.cooldown_ms / 1000.0)
        log.debug("EchoProtection: TTS beendet, Cooldown %d ms", self._config.cooldown_ms)

    def is_suppressed(self) -> bool:
        """Return True if wake word processing should be skipped."""
        return self._tts_active or time.monotonic() < self._cooldown_until

    def estimate_mic_energy(self, chunk: np.ndarray) -> float:
        """Return normalised RMS energy of a microphone chunk."""
        if chunk.size == 0:
            return 0.0
        samples = chunk.astype(np.float64)
        rms = np.sqrt(np.mean(samples ** 2))
        # Normalise roughly to 0..1 for 16-bit audio.
        return min(1.0, rms / 32768.0)

    def record_reference_energy(self, chunk: np.ndarray) -> None:
        """Store the energy of the current TTS output chunk as reference."""
        self._reference_energy = self.estimate_mic_energy(chunk)

    def detect_echo_risk(self, mic_chunk: np.ndarray) -> bool:
        """Return True if microphone input looks like an echo of TTS output."""
        if not self._tts_active:
            return False
        mic_energy = self.estimate_mic_energy(mic_chunk)
        # If mic energy is close to the reference TTS energy, we assume echo.
        if self._reference_energy > 0 and mic_energy > self._reference_energy * 0.5:
            log.debug("EchoProtection: Echo-Risiko erkannt (mic=%.3f, ref=%.3f)", mic_energy, self._reference_energy)
            return True
        if mic_energy > self._config.energy_threshold:
            log.debug("EchoProtection: Mikrofon-Energie hoch (%.3f)", mic_energy)
            return True
        return False
