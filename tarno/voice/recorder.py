"""Local voice recording with metadata and consent tracking."""

from __future__ import annotations

import json
import logging
import wave
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

log = logging.getLogger(__name__)


@dataclass
class Recording:
    path: Path
    purpose: str
    started_at: datetime
    consent: str
    metadata_path: Path


class VoiceRecorder:
    """Records microphone audio to WAV files under the user's home directory."""

    def __init__(self, base_dir: Path | str = "~/.tarno/recordings") -> None:
        self._base_dir = Path(base_dir).expanduser()
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._current: Recording | None = None
        self._frames: list[bytes] = []
        self._sample_rate: int = 16000
        self._channels: int = 1
        self._sample_width: int = 2

    def start(
        self,
        purpose: str,
        consent: str = "once",
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> Recording:
        if self._current is not None:
            raise RuntimeError("Aufnahme läuft bereits")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recording_{timestamp}.wav"
        path = self._base_dir / filename
        metadata_path = path.with_suffix(".json")

        self._current = Recording(
            path=path,
            purpose=purpose,
            started_at=datetime.now(),
            consent=consent,
            metadata_path=metadata_path,
        )
        self._frames = []
        self._sample_rate = sample_rate
        self._channels = channels
        log.info("Aufnahme gestartet: %s (Zweck: %s)", path, purpose)
        return self._current

    def add_frames(self, frames: bytes) -> None:
        if self._current is None:
            return
        self._frames.append(frames)

    def add_numpy(self, data: np.ndarray) -> None:
        if data.dtype != np.int16:
            data = data.astype(np.int16)
        self.add_frames(data.tobytes())

    def stop(self) -> Recording:
        if self._current is None:
            raise RuntimeError("Keine aktive Aufnahme")

        recording = self._current
        self._write_wav(recording.path)
        self._write_metadata(recording)

        self._current = None
        self._frames = []
        log.info("Aufnahme gespeichert: %s", recording.path)
        return recording

    def _write_wav(self, path: Path) -> None:
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(self._channels)
            wf.setsampwidth(self._sample_width)
            wf.setframerate(self._sample_rate)
            for frame in self._frames:
                wf.writeframes(frame)

    def _write_metadata(self, recording: Recording) -> None:
        metadata: dict[str, Any] = {
            "purpose": recording.purpose,
            "started_at": recording.started_at.isoformat(),
            "consent": recording.consent,
            "sample_rate": self._sample_rate,
            "channels": self._channels,
            "file": str(recording.path),
        }
        recording.metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def is_recording(self) -> bool:
        return self._current is not None

    def delete(self, recording: Recording) -> None:
        recording.path.unlink(missing_ok=True)
        recording.metadata_path.unlink(missing_ok=True)
        log.info("Aufnahme gelöscht: %s", recording.path)
