"""Tests for tarno/voice/adaptive_listener.py.

Covers the sentence-completeness heuristic (unchanged, used by the in-chat
Diktat feature's trailing-extension logic) and a regression test for the
resumption-chunk debounce fix (Phase B): a single audible spike (e.g. one
breath/inhale) during a silence gap used to immediately reset the silence
counter via a single above-threshold chunk, artificially extending long
dictation pauses. Now it takes _MIN_RESUMPTION_CHUNKS consecutive
above-threshold chunks before the silence counter is reset.
"""

from __future__ import annotations

import unittest

import numpy as np

from tarno.core.config import VADConfig, vad_config_for_eagerness
from tarno.voice.adaptive_listener import AdaptiveListener, sentence_seems_incomplete


class SentenceSeemsIncompleteTests(unittest.TestCase):
    def test_empty_text_is_incomplete(self) -> None:
        self.assertTrue(sentence_seems_incomplete(""))

    def test_trailing_conjunction_is_incomplete(self) -> None:
        self.assertTrue(sentence_seems_incomplete("Ich gehe heute und"))

    def test_trailing_comma_is_incomplete(self) -> None:
        self.assertTrue(sentence_seems_incomplete("Erstens,"))

    def test_complete_sentence_is_not_incomplete(self) -> None:
        self.assertFalse(sentence_seems_incomplete("Das Wetter ist heute schön."))


class VadConfigForEagernessTests(unittest.TestCase):
    def test_low_is_most_patient(self) -> None:
        cfg = vad_config_for_eagerness("low")
        self.assertEqual(cfg.silence_threshold_sec, 12.0)
        self.assertEqual(cfg.max_extensions, 5)

    def test_high_is_most_eager(self) -> None:
        cfg = vad_config_for_eagerness("high")
        self.assertEqual(cfg.silence_threshold_sec, 5.0)
        self.assertEqual(cfg.max_extensions, 2)

    def test_unknown_falls_back_to_medium(self) -> None:
        self.assertEqual(vad_config_for_eagerness("unknown"), vad_config_for_eagerness("medium"))


class _ScriptedStream:
    """Fake stream feeding a pre-scripted sequence of single-sample chunks,
    falling back to an indefinite quiet tail once the script is exhausted."""

    def __init__(self, chunks: list[np.ndarray], fallback: np.ndarray) -> None:
        self._chunks = list(chunks)
        self._fallback = fallback

    def read_chunk(self) -> np.ndarray:
        if self._chunks:
            return self._chunks.pop(0)
        return self._fallback


def _make_listener() -> AdaptiveListener:
    cfg = VADConfig(
        silence_threshold_sec=1.0,
        min_speech_duration_sec=0.0,
        max_speech_duration_sec=100.0,
        trailing_extension_sec=0.0,
        max_extensions=0,
        energy_floor=100.0,
        onset_factor=1.0,
        listen_timeout=1000.0,
    )
    # sample_rate=8, chunk_size=1 -> 8 chunks/sec, so silence_threshold_sec=1.0
    # maps to exactly 8 chunks - easy to reason about per-chunk in the test.
    return AdaptiveListener(sample_rate=8, chunk_size=1, vad_config=cfg)


class ResumptionDebounceTests(unittest.TestCase):
    quiet = np.array([0], dtype=np.int16)
    loud = np.array([150], dtype=np.int16)

    def test_single_spike_during_silence_does_not_reset_silence_counter(self) -> None:
        script = (
            [self.quiet] * 2       # pre-roll before onset
            + [self.loud]          # onset (triggers speech_on, chunk itself dropped)
            + [self.quiet] * 7     # silence_n climbs to 7 (of 8 needed)
            + [self.loud]          # single spike - must NOT reset silence_n
            + [self.quiet] * 5     # one more quiet chunk should now cut off
        )
        listener = _make_listener()
        stream = _ScriptedStream(script, fallback=self.quiet)

        result = listener.listen(stream)

        self.assertIsNotNone(result)
        # 2 pre-roll + 7 quiet + 1 spike + 1 quiet (the chunk that pushes
        # silence_n to 8 and breaks) = 11. Without the debounce fix, the
        # spike alone would reset silence_n to 0 and force 8 MORE quiet
        # chunks (total 18) before cutting off.
        self.assertEqual(len(result), 11)

    def test_no_spike_cuts_off_after_exactly_the_silence_limit(self) -> None:
        script = [self.quiet] * 2 + [self.loud] + [self.quiet] * 8
        listener = _make_listener()
        stream = _ScriptedStream(script, fallback=self.quiet)

        result = listener.listen(stream)

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 10)


if __name__ == "__main__":
    unittest.main()
