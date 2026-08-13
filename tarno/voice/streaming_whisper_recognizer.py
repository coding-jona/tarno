"""Speech-to-text with faster-whisper, using simple volume-threshold speech
detection (EnergyVAD) - not Silero/real-time, matches the classic
record-until-silence-then-transcribe-once flow that worked reliably before."""

from __future__ import annotations

import logging
import tempfile
import time
import wave
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from tarno.voice.audio_stream import AudioStream
from tarno.voice.audio_utils import AutomaticGainControl

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

    from tarno.core.config import AGCConfig, AudioConfig

log = logging.getLogger(__name__)

_VAD_CHUNK_SAMPLES = 512
_VAD_SAMPLE_RATE = 16000
_OVERLAP_MS = 1000
_OVERLAP_BYTES = int(_OVERLAP_MS * _VAD_SAMPLE_RATE / 1000) * 2  # 16-bit mono


class EnergyVAD:
    """RMS-threshold speech-onset detector - replaces the earlier Silero VAD
    neural model here on purpose, per two confirmed reasons (found live):

    1. Reliability: Silero VAD's "start" event repeatedly failed to fire even
       with confirmed real, AGC-boosted, non-silent microphone signal
       (RMS up to ~25000/32767), causing every post-wake-word capture to time
       out with nothing transcribed.
    2. Cost: this runs continuously while listening, on whatever hardware
       TARNO ships to - a neural VAD model doing per-chunk inference is
       meaningfully heavier than an RMS comparison; the product needs to run
       acceptably on weak laptops, not just a powerful dev machine.

    Only detects speech onset ("start"); end-of-utterance is left to the
    existing silence-duration timeout below in listen_stream (same shape as
    the classic sr.Recognizer.pause_threshold behavior this restores)."""

    def __init__(self, energy_threshold: float) -> None:
        self._threshold = energy_threshold
        self._triggered = False

    def reset(self) -> None:
        self._triggered = False

    def process_chunk(self, pcm_bytes: bytes) -> dict[str, int] | None:
        if self.is_speech(pcm_bytes) and not self._triggered:
            self._triggered = True
            return {"start": 0}
        return None

    def is_speech(self, pcm_bytes: bytes) -> bool:
        """Stateless per-chunk check, used by listen_stream to decide whether
        the current chunk still counts as speech for silence-timeout purposes
        (separate from process_chunk's one-shot "start" transition)."""
        samples = np.frombuffer(pcm_bytes, dtype=np.int16)
        if samples.size == 0:
            return False
        rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
        return rms >= self._threshold


class StreamingWhisperRecognizer:
    """STT: captures audio in chunks, detects speech onset by volume
    (EnergyVAD), and transcribes the completed utterance once (after enough
    silence) with faster-whisper.
    """

    def __init__(
        self,
        config: AudioConfig,
        model: "WhisperModel | None" = None,
        vad_config: dict[str, Any] | None = None,
        agc_config: AGCConfig | None = None,
    ) -> None:
        self._config = config
        self._timeout = config.listen_timeout
        self._phrase_limit = config.phrase_time_limit
        self._silence_sec = getattr(config, "silence_threshold_sec", 1.8)
        self._min_speech_sec = getattr(config, "min_speech_duration_sec", 0.3)

        self._vad = EnergyVAD(config.energy_threshold)
        self._agc = AutomaticGainControl(agc_config) if agc_config and agc_config.enabled else None

        if model is not None:
            self._model = model
        else:
            import faster_whisper

            cache_dir = Path.home() / ".cache" / "faster-whisper"
            cache_dir.mkdir(parents=True, exist_ok=True)
            self._model = faster_whisper.WhisperModel(
                config.whisper_model,
                device="cpu",
                compute_type="int8",
                cpu_threads=4,
                download_root=str(cache_dir),
            )

    def listen_stream(
        self,
        audio_stream: AudioStream,
        partial_callback: Callable[[str], None] | None = None,
    ) -> str | None:
        """Listen until an utterance is complete and return the transcription."""
        self._vad.reset()
        buffer = bytearray()
        overlap = bytearray()
        triggered = False
        started_at = time.monotonic()
        last_speech_at = started_at

        log.info("Lausche (Lautstärke-Erkennung)...")

        while True:
            try:
                chunk = audio_stream.read_frames(_VAD_CHUNK_SAMPLES)
            except RuntimeError:
                log.exception("AudioStream Lesefehler im STT-Stream")
                raise

            now = time.monotonic()
            if now - started_at > self._timeout:
                # Found live: speech starting late in the window (e.g. a
                # brief pause after the wake word before the user actually
                # speaks) could get captured into `buffer` and then discarded
                # here untranscribed, because the absolute timeout fired
                # before the silence_sec gap had time to elapse naturally.
                # If we already have real captured audio, transcribe it
                # instead of throwing it away.
                if triggered and len(buffer) > 0:
                    log.info(
                        "STT Timeout nach %ds, aber Sprache erfasst - transkribiere trotzdem",
                        self._timeout,
                    )
                    return self._transcribe(bytes(buffer))
                log.info("STT Timeout nach %ds", self._timeout)
                return None

            if log.isEnabledFor(logging.DEBUG):
                raw_rms = float(np.sqrt(np.mean(np.frombuffer(chunk, dtype=np.int16).astype(np.float64) ** 2)))
                log.debug("STT-Chunk RMS (roh, vor AGC)=%.0f, len=%d", raw_rms, len(chunk))

            if self._agc is not None:
                chunk = self._agc.apply(np.frombuffer(chunk, dtype=np.int16)).tobytes()

            if log.isEnabledFor(logging.DEBUG):
                rms = float(np.sqrt(np.mean(np.frombuffer(chunk, dtype=np.int16).astype(np.float64) ** 2)))
                log.debug("STT-Chunk RMS (nach AGC)=%.0f", rms)

            result = self._vad.process_chunk(chunk)

            if result is not None and "start" in result and not triggered:
                triggered = True
                buffer = overlap + bytearray(chunk)
                last_speech_at = now
                if partial_callback:
                    partial_callback("")
            elif triggered:
                buffer.extend(chunk)
                # BUG FIX (found live): this used to unconditionally reset
                # last_speech_at to `now` every iteration, before checking
                # `now - last_speech_at > silence_sec` below - that check was
                # always comparing 0 > silence_sec, i.e. always false, so the
                # silence-timeout branch could never fire. Only reset it when
                # the current chunk is still actually loud, so elapsed
                # silence can genuinely accumulate.
                if self._vad.is_speech(chunk):
                    last_speech_at = now

                if now - last_speech_at > self._silence_sec:
                    return self._transcribe(bytes(buffer))

                if len(buffer) >= self._phrase_limit * _VAD_SAMPLE_RATE * 2:
                    return self._transcribe(bytes(buffer))
            else:
                overlap.extend(chunk)
                if len(overlap) > _OVERLAP_BYTES:
                    overlap = overlap[-_OVERLAP_BYTES:]

    def _transcribe(self, audio_bytes: bytes) -> str | None:
        """Transcribe a completed utterance with faster-whisper."""
        if not audio_bytes:
            return None

        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                wav_path = Path(tmp.name)

            with wave.open(str(wav_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(_VAD_SAMPLE_RATE)
                wav.writeframes(audio_bytes)

            segments, _ = self._model.transcribe(
                str(wav_path),
                language=self._config.language,
                task="transcribe",
                vad_filter=False,  # EnergyVAD already handled segmentation.
                beam_size=self._config.whisper_beam_size,
                condition_on_previous_text=self._config.whisper_condition_on_previous_text,
                initial_prompt=self._config.whisper_initial_prompt or None,
            )
            text = " ".join(s.text for s in segments).strip()
            if not text:
                return None
            log.info("Erkannt (streaming-whisper): %s", text)
            return text
        except Exception:
            log.exception("Streaming Transkription fehlgeschlagen")
            return None
