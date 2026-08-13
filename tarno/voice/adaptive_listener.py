"""Adaptive speech listener with dynamic silence timeout.

Replaces sr.Recognizer.listen() with a smarter pipeline that:
- Uses energy-based VAD with configurable silence threshold (1.5-2.0s)
- Extends listening on incomplete German sentences (trailing conjunctions, fillers)
- Applies a simple noise gate to reduce ambient noise impact on VAD
- Maintains a pre-roll buffer to avoid clipping onset consonants
"""

from __future__ import annotations

import io
import logging
import wave
from typing import TYPE_CHECKING, Callable

import numpy as np

from tarno.voice.audio_utils import AutomaticGainControl

if TYPE_CHECKING:
    from tarno.core.config import AGCConfig, VADConfig
    from tarno.voice.audio_stream import AudioStream

log = logging.getLogger(__name__)

_TRAILING_INCOMPLETE: frozenset[str] = frozenset({
    "und", "oder", "aber", "sondern", "denn", "weil", "dass", "ob",
    "wenn", "als", "obwohl", "damit", "bevor", "nachdem", "während",
    "bis", "seit", "seitdem", "falls", "sofern", "sobald", "solange",
    "indem", "sodass", "anstatt", "statt", "ohne",
    "der", "die", "das", "welcher", "welche", "welches",
    "mit", "von", "für", "über", "unter", "auf", "in", "an",
    "bei", "nach", "zu", "aus", "durch", "gegen", "um",
    "äh", "ähm", "also", "halt", "quasi", "sozusagen", "naja",
    "hm", "hmm", "ja", "nee", "ne",
    "ein", "eine", "einen", "einem", "einer", "eines",
    "ich", "du", "er", "sie", "es", "wir", "ihr",
})


def sentence_seems_incomplete(text: str) -> bool:
    """Heuristic: does a German text fragment appear unfinished?"""
    text = text.strip()
    if not text:
        return True
    if text.endswith((",", "-", "–", "...")):
        return True
    last_word = text.split()[-1].lower().rstrip(".,!?;:")
    return last_word in _TRAILING_INCOMPLETE


def _rms(chunk: np.ndarray) -> float:
    return float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))


class AdaptiveListener:
    """Captures a single utterance from an AudioStream with adaptive silence handling.

    Unlike sr.Recognizer.listen(), this listener:
    - Separates onset detection from end-of-utterance detection
    - Allows a configurable silence duration (1.5-2.0s) before cutting off
    - Optionally extends listening when a partial transcript looks incomplete
    - Applies a simple noise gate to stabilise the energy-based VAD
    """

    # Requires this many CONSECUTIVE above-threshold chunks before treating
    # speech as resumed, instead of a single chunk instantly resetting the
    # silence counter - a lone audible breath/inhale during a pause used to
    # zero out silence_n on its own, artificially extending long dictation
    # pauses (Phase B: In-Chat-Diktat).
    _MIN_RESUMPTION_CHUNKS = 2

    def __init__(
        self,
        sample_rate: int,
        chunk_size: int,
        vad_config: VADConfig,
        partial_transcribe: Callable[[np.ndarray], str | None] | None = None,
        agc_config: "AGCConfig | None" = None,
    ) -> None:
        self._sample_rate = sample_rate
        self._chunk_size = chunk_size
        self._cfg = vad_config
        self._partial_transcribe = partial_transcribe

        self._noise_floor_rms: float = vad_config.energy_floor
        self._onset_threshold: float = vad_config.energy_floor * vad_config.onset_factor

        # Same "künstlicher Mikrofonverstärker" used during wake-word
        # listening (tarno/voice/wakeword.py) - applied here too so a
        # far-field wake-word trigger is followed by an actually usable
        # far-field command capture, instead of reverting to the raw (quiet)
        # signal the moment the wake word fires. Own instance/EMA state,
        # separate from the wake-word detector's.
        if agc_config is None:
            from tarno.core.config import AGCConfig
            agc_config = AGCConfig()
        self._agc_enabled = agc_config.enabled
        self._agc = AutomaticGainControl(agc_config)

    def _read_chunk(self, stream: AudioStream) -> np.ndarray:
        chunk = stream.read_chunk()
        return self._agc.apply(chunk) if self._agc_enabled else chunk

    def calibrate(self, stream: AudioStream, duration: float = 0.8) -> None:
        """Estimate ambient noise RMS from a short silence window."""
        samples_needed = int(self._sample_rate * duration)
        collected = 0
        rms_values: list[float] = []

        while collected < samples_needed:
            chunk = self._read_chunk(stream)
            rms_values.append(_rms(chunk))
            collected += len(chunk)

        if rms_values:
            avg = sum(rms_values) / len(rms_values)
            self._noise_floor_rms = max(avg * 1.5, self._cfg.energy_floor)
            self._onset_threshold = self._noise_floor_rms * self._cfg.onset_factor
            log.info(
                "AdaptiveListener kalibriert: noise_floor=%.1f, onset=%.1f",
                self._noise_floor_rms,
                self._onset_threshold,
            )

    def listen(self, stream: AudioStream) -> np.ndarray | None:
        """Block until a complete utterance is captured.

        Returns int16 PCM numpy array, or None on timeout.
        """
        cps = self._sample_rate / self._chunk_size
        max_wait = int(self._cfg.listen_timeout * cps)
        silence_limit = int(self._cfg.silence_threshold_sec * cps)
        min_speech = int(self._cfg.min_speech_duration_sec * cps)
        max_speech = int(self._cfg.max_speech_duration_sec * cps)
        ext_limit = int(self._cfg.trailing_extension_sec * cps)
        pre_roll_n = max(2, int(0.15 * cps))

        speech_on = False
        silence_n = 0
        resumption_n = 0
        waited = 0
        ext_used = 0
        buf: list[np.ndarray] = []
        pre_roll: list[np.ndarray] = []

        # Fresh gain per utterance - don't carry over EMA state from a
        # previous turn where the user may have been standing somewhere
        # else entirely.
        self._agc.reset()

        log.debug(
            "AdaptiveListener.listen(): silence=%.2fs, onset=%.0f, max_ext=%d",
            self._cfg.silence_threshold_sec,
            self._onset_threshold,
            self._cfg.max_extensions,
        )

        while waited < max_wait:
            try:
                raw = self._read_chunk(stream)
            except Exception:
                log.exception("Audio-Lesefehler im AdaptiveListener")
                return None

            chunk_rms = _rms(raw)
            waited += 1

            if not speech_on:
                pre_roll.append(raw)
                if len(pre_roll) > pre_roll_n:
                    pre_roll.pop(0)
                if chunk_rms >= self._onset_threshold:
                    speech_on = True
                    silence_n = 0
                    buf.extend(pre_roll)
                    pre_roll.clear()
                    log.debug("Sprachbeginn erkannt (RMS=%.0f)", chunk_rms)
                continue

            buf.append(raw)

            if chunk_rms < self._noise_floor_rms:
                silence_n += 1
                resumption_n = 0
            else:
                resumption_n += 1
                if resumption_n >= self._MIN_RESUMPTION_CHUNKS:
                    silence_n = 0

            if len(buf) >= max_speech:
                log.info(
                    "Maximale Sprachdauer erreicht (%.1fs)",
                    self._cfg.max_speech_duration_sec,
                )
                break

            if silence_n < silence_limit:
                continue

            if len(buf) < min_speech:
                log.debug("Zu kurz, ignoriere")
                speech_on = False
                silence_n = 0
                buf.clear()
                continue

            if self._try_extend(stream, buf, ext_used, ext_limit):
                ext_used += 1
                silence_n = 0
                continue

            log.debug("Stille-Schwelle erreicht (%.2fs)", self._cfg.silence_threshold_sec)
            break

        if not buf:
            log.info("Keine Sprache erkannt (Timeout nach %.0fs)", self._cfg.listen_timeout)
            return None

        result = np.concatenate(buf)
        dur = len(result) / self._sample_rate
        log.info("Aufnahme abgeschlossen: %.2fs, %d Extensions", dur, ext_used)
        return result

    def _try_extend(
        self,
        stream: AudioStream,
        buf: list[np.ndarray],
        ext_used: int,
        ext_limit: int,
    ) -> bool:
        """Check sentence completeness; if incomplete, extend the listening window.

        Returns True if extension was granted (caller resets silence counter).
        """
        if self._partial_transcribe is None:
            return False
        if ext_used >= self._cfg.max_extensions:
            return False

        combined = np.concatenate(buf)
        text = self._partial_transcribe(combined)
        if not text or not sentence_seems_incomplete(text):
            return False

        log.info(
            "Satz unvollständig (\"%s\"), verlängere (+%.1fs, %d/%d)",
            text[-50:],
            self._cfg.trailing_extension_sec,
            ext_used + 1,
            self._cfg.max_extensions,
        )

        ext_waited = 0
        while ext_waited < ext_limit:
            try:
                ext_chunk = self._read_chunk(stream)
            except Exception:
                break
            buf.append(ext_chunk)
            if _rms(ext_chunk) >= self._noise_floor_rms:
                return True
            ext_waited += 1

        return True

    @staticmethod
    def pcm_to_wav_bytes(pcm: np.ndarray, sample_rate: int) -> bytes:
        """Convert int16 PCM numpy array to in-memory WAV."""
        out = io.BytesIO()
        with wave.open(out, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm.tobytes())
        return out.getvalue()
