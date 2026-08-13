"""Tests for the shared AutomaticGainControl ("künstlicher Mikrofonverstärker"),
used by both wake-word listening and post-wake-word speech capture."""

from __future__ import annotations

import unittest

import numpy as np

from tarno.core.config import AGCConfig
from tarno.voice.audio_utils import AutomaticGainControl


def _quiet_chunk(rms: float, length: int = 1280) -> np.ndarray:
    return np.full(length, int(rms), dtype=np.int16)


class AutomaticGainControlTests(unittest.TestCase):
    def test_boosts_quiet_chunk_toward_target_rms(self) -> None:
        agc = AutomaticGainControl(AGCConfig(target_rms=3000.0, max_gain=8.0, attack=1.0))
        chunk = _quiet_chunk(rms=200)
        boosted = agc.apply(chunk)

        self.assertEqual(boosted.dtype, np.int16)
        boosted_rms = float(np.sqrt(np.mean(boosted.astype(np.float64) ** 2)))
        original_rms = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))
        self.assertGreater(boosted_rms, original_rms)

    def test_clamps_gain_to_max_gain(self) -> None:
        agc = AutomaticGainControl(AGCConfig(target_rms=3000.0, max_gain=8.0, attack=1.0))
        chunk = _quiet_chunk(rms=10)  # naive ratio (3000/10=300) far exceeds max_gain
        boosted = agc.apply(chunk)

        ratio = float(boosted[0]) / float(chunk[0])
        self.assertAlmostEqual(ratio, 8.0, places=1)

    def test_damps_already_loud_signal_toward_target(self) -> None:
        """rms well above target_rms should pull gain down (capped at 0.5x
        floor), not leave the signal untouched - the point is to avoid the
        gain getting "stuck" high after a loud event and then distorting a
        subsequent quiet wake word."""
        agc = AutomaticGainControl(AGCConfig(target_rms=3000.0, max_gain=8.0, attack=1.0))
        chunk = _quiet_chunk(rms=10000)  # well above target
        boosted = agc.apply(chunk)

        self.assertLess(int(boosted[0]), int(chunk[0]))
        ratio = float(boosted[0]) / float(chunk[0])
        self.assertGreaterEqual(ratio, 0.5)

    def test_handles_silence_without_division_error(self) -> None:
        agc = AutomaticGainControl(AGCConfig())
        chunk = np.zeros(1280, dtype=np.int16)
        result = agc.apply(chunk)

        np.testing.assert_array_equal(result, chunk)
        self.assertFalse(np.any(np.isnan(result.astype(np.float64))))

    def test_clips_to_int16_range_without_wraparound(self) -> None:
        agc = AutomaticGainControl(AGCConfig(target_rms=3000.0, max_gain=8.0, attack=1.0))
        chunk = _quiet_chunk(rms=20000)  # loud enough that gain=1.0 could still overflow at peaks
        chunk[0] = 30000
        boosted = agc.apply(chunk)

        self.assertTrue(np.all(boosted <= 32767))
        self.assertTrue(np.all(boosted >= -32768))

    def test_smoothing_uses_ema_across_chunks(self) -> None:
        agc = AutomaticGainControl(AGCConfig(target_rms=3000.0, max_gain=8.0, attack=0.5))

        agc.apply(_quiet_chunk(rms=3000))  # gain settles near 1.0
        gain_after_first = agc._gain

        agc.apply(_quiet_chunk(rms=200))  # instantaneous gain would jump to 8.0 (capped)
        gain_after_second = agc._gain

        self.assertGreater(gain_after_second, gain_after_first)
        self.assertLess(gain_after_second, 8.0)

    def test_reset_returns_gain_to_unity(self) -> None:
        agc = AutomaticGainControl(AGCConfig(target_rms=3000.0, max_gain=8.0, attack=1.0))
        agc.apply(_quiet_chunk(rms=10))  # push gain up toward max
        self.assertGreater(agc._gain, 1.0)

        agc.reset()
        self.assertEqual(agc._gain, 1.0)


if __name__ == "__main__":
    unittest.main()
