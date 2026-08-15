"""Shared audio-processing helpers used across the voice pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from tarno_backend.core.config import AGCConfig


class AutomaticGainControl:
    """RMS-based software gain stage ("künstlicher Mikrofonverstärker").

    Boosts quiet chunks toward target_rms, but also allows damping loud
    chunks (down to a 0.5x floor) so the gain doesn't get stuck high after a
    loud event and then distort a subsequent quiet wake word. Capped at
    max_gain (prevents amplifying pure noise into false triggers), smoothed
    via EMA with a faster attack than release.

    Stateful per instance (self._gain persists across apply() calls) -
    each consumer (wake-word listening, post-wake-word speech capture) must
    hold its own instance rather than sharing one, since they run at
    different points in the pipeline and would otherwise fight over the
    same EMA state.
    """

    def __init__(self, config: "AGCConfig") -> None:
        self._target_rms = config.target_rms
        self._max_gain = config.max_gain
        self._attack = config.attack
        self._gain = 1.0

    def apply(self, audio_chunk: np.ndarray) -> np.ndarray:
        """Apply the current gain to one chunk, adapting the gain toward
        target_rms for next time. Silent (near-zero RMS) chunks pass through
        unchanged rather than getting amplified into noise."""
        rms = float(np.sqrt(np.mean(audio_chunk.astype(np.float64) ** 2)))
        if rms < 1e-6:
            return audio_chunk

        target_gain = min(self._target_rms / rms, self._max_gain)
        # Erlaube leichte Dämpfung (bis ca. -6 dB), um plötzliche Lautstärken
        # nicht hart zu clippen, wenn der Gain gerade noch hoch steht.
        target_gain = max(target_gain, 0.5)

        # Schnelles Hochfahren bei leisen Signalen, schnelles Absenken bei
        # lauten Signalen - verhindert das "Hängenbleiben" des Gains.
        coeff = self._attack if target_gain > self._gain else 0.35
        self._gain = coeff * target_gain + (1 - coeff) * self._gain
        self._gain = float(np.clip(self._gain, 0.5, self._max_gain))

        amplified = audio_chunk.astype(np.float64) * self._gain
        clipped = np.clip(amplified, -32768, 32767)
        return clipped.astype(np.int16)

    def reset(self) -> None:
        """Drop back to unity gain (e.g. when starting a fresh listen)."""
        self._gain = 1.0
