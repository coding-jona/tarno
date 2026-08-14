"""Piper TTS engine: fast local CPU synthesis with ONNX models."""

from __future__ import annotations

import logging
import wave
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
from huggingface_hub import hf_hub_download

from tarno_backend.voice.tts_engines.base import BaseTTSEngine, TTSAudioChunk

log = logging.getLogger(__name__)


_PIPER_MODELS_DIR = Path.home() / ".tarno" / "models" / "piper"

# Standard-Repo auf HF (gültiges Piper ONNX Repository)
_DEFAULT_REPO = "Trelis/piper-de-de-thorsten-medium"
_DEFAULT_MODEL = "model.onnx"


class PiperEngine(BaseTTSEngine):
    """Piper TTS via piper-tts.

    Models are lazily downloaded from HuggingFace if ``voice`` is a repository
    ID, otherwise a local ``.onnx`` path is loaded directly.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._voice = str(config.get("voice", _DEFAULT_REPO))
        self._model_path, self._config_path = self._resolve_model_files()
        self._voice_obj = self._load_voice()

    @property
    def name(self) -> str:
        return "piper"

    @property
    def sample_rate(self) -> int:
        if self._voice_obj is not None:
            return int(self._voice_obj.config.sample_rate)
        return 22050

    @property
    def sample_width(self) -> int:
        return 2

    @property
    def num_channels(self) -> int:
        return 1

    @property
    def supports_streaming(self) -> bool:
        return self._voice_obj is not None

    def close(self) -> None:
        self._voice_obj = None

    def _resolve_model_files(self) -> tuple[Path, Path]:
        """Return (model.onnx, config.json) paths, downloading if needed."""
        voice = self._voice

        # 1. Lokale Datei direkt laden
        candidate = Path(voice).expanduser()
        if candidate.exists():
            model_path = candidate
            config_path = candidate.parent / f"{candidate.name}.json"
            if not config_path.exists():
                config_path = candidate.with_suffix(".json")
            return model_path, config_path

        # 2. Guardrail: Vermeidet HTTP 401 bei HF durch unpassende IDs (z.B. Edge-TTS 'de-DE-ConradNeural')
        if "Neural" in voice or "/" not in voice:
            log.warning(
                "Ungültige Piper Voice-ID oder Fremdmodell '%s' erkannt. Falle zurück auf '%s'.",
                voice,
                _DEFAULT_REPO,
            )
            voice = _DEFAULT_REPO

        # 3. Pfad- und Repo-Parsing für HuggingFace
        repo_id = voice
        model_filename = _DEFAULT_MODEL

        # Falls ein tieferer Pfad übergeben wurde (z.B. rhasspy/piper-voices/de/.../model.onnx)
        if any(repo_id.endswith(ext) for ext in (".onnx", ".pt")):
            parts = repo_id.split("/")
            repo_id = "/".join(parts[:2])
            model_filename = "/".join(parts[2:])

        # Config-Varianten auflösen
        if model_filename.endswith(".onnx"):
            base_name = model_filename[:-5]
            primary_config = f"{base_name}.json"        # z. B. model.json
            fallback_config = f"{model_filename}.json"  # z. B. model.onnx.json
        else:
            primary_config = f"{model_filename}.json"
            fallback_config = f"{model_filename}.onnx.json"

        _PIPER_MODELS_DIR.mkdir(parents=True, exist_ok=True)

        log.info("Lade Piper-Modell '%s' (%s) herunter...", repo_id, model_filename)
        try:
            local_model = Path(
                hf_hub_download(
                    repo_id=repo_id,
                    filename=model_filename,
                    local_dir=str(_PIPER_MODELS_DIR),
                )
            )

            # Versuche primäre Config, sonst Fallback
            try:
                local_config = Path(
                    hf_hub_download(
                        repo_id=repo_id,
                        filename=primary_config,
                        local_dir=str(_PIPER_MODELS_DIR),
                    )
                )
            except Exception:
                log.debug("Primary config '%s' fehlgeschlagen, versuche Fallback '%s'", primary_config, fallback_config)
                local_config = Path(
                    hf_hub_download(
                        repo_id=repo_id,
                        filename=fallback_config,
                        local_dir=str(_PIPER_MODELS_DIR),
                    )
                )

        except Exception:
            log.exception("Piper-Modell-Download fehlgeschlagen: %s", repo_id)
            raise

        return local_model, local_config

    def _load_voice(self) -> Any:
        try:
            from piper import PiperVoice

            return PiperVoice.load(str(self._model_path), str(self._config_path))
        except Exception:
            log.exception("Piper-Stimme konnte nicht geladen werden")
            raise

    def synthesize_stream(self, text: str) -> Iterator[TTSAudioChunk]:
        """Yield audio chunks as Piper synthesizes them."""
        if self._voice_obj is None:
            raise RuntimeError("Piper-Stimme nicht verfügbar")

        try:
            for chunk in self._voice_obj.synthesize(text):
                yield TTSAudioChunk(
                    audio_bytes=chunk.audio_int16_bytes,
                    sample_rate=self.sample_rate,
                    sample_width=self.sample_width,
                    num_channels=self.num_channels,
                )
        except Exception:
            log.exception("Piper-Synthese fehlgeschlagen")
            raise

    def synthesize_to_file(self, text: str, output_path: Path) -> bool:
        """Synthesize the full text into a WAV file."""
        try:
            sample_rate = self.sample_rate
            samples: list[np.ndarray] = []
            for chunk in self.synthesize_stream(text):
                audio = np.frombuffer(chunk.audio_bytes, dtype=np.int16)
                samples.append(audio)

            if not samples:
                return False

            full = np.concatenate(samples)
            with wave.open(str(output_path), "wb") as wav_file:
                wav_file.setnchannels(self.num_channels)
                wav_file.setsampwidth(self.sample_width)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(full.tobytes())
            return True
        except Exception:
            log.exception("Piper Dateisynthese fehlgeschlagen")
            return False