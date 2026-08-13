"""Abstract base class for local TTS engines."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TTSAudioChunk:
    """A single chunk of synthesized PCM audio."""

    audio_bytes: bytes
    sample_rate: int
    sample_width: int
    num_channels: int

    @property
    def duration_sec(self) -> float:
        """Return the duration of this chunk in seconds."""
        bytes_per_frame = self.num_channels * self.sample_width
        frames = len(self.audio_bytes) // bytes_per_frame
        if self.sample_rate == 0:
            return 0.0
        return frames / self.sample_rate


class BaseTTSEngine(ABC):
    """Common interface for all TTS engines.

    Engines must provide their native sample rate, support streaming if they
    can produce audio chunks before the full text is finished, and fall back to
    whole-file synthesis if streaming is disabled or fails.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Engine identifier used in logs and config."""

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Native output sample rate in Hz."""

    @property
    @abstractmethod
    def sample_width(self) -> int:
        """Bytes per sample (e.g. 2 for 16-bit PCM)."""

    @property
    @abstractmethod
    def num_channels(self) -> int:
        """Number of audio channels (1 for mono)."""

    @property
    def supports_streaming(self) -> bool:
        """Whether the engine can produce audio while synthesizing."""
        return False

    @property
    def supports_voice_cloning(self) -> bool:
        """Whether the engine can clone a voice from a reference sample."""
        return False

    @abstractmethod
    def synthesize_stream(self, text: str) -> Iterator[TTSAudioChunk]:
        """Yield audio chunks as they become available.

        If the engine does not natively stream, it may synthesize the whole
        text and yield a single chunk.
        """

    @abstractmethod
    def synthesize_to_file(self, text: str, output_path: Path) -> bool:
        """Synthesize the full text to a file.

        Returns True on success. The file format is engine-specific but must be
        playable by the existing pygame/SpeechSynthesizer fallback path.
        """

    def close(self) -> None:
        """Release any loaded model/session before this engine is discarded.

        Called by SpeechSynthesizer._init_engines() on the previous engine set
        before replacing it (e.g. on a language switch) so a loaded model
        (like Piper's ONNX session) doesn't linger until GC. No-op by default
        for engines with no local resource to release (e.g. EdgeTTSEngine).
        """
