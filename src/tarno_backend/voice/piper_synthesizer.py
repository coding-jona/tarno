"""Text-to-speech output via Piper TTS (local, fast)."""

from __future__ import annotations

import logging
import os
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from tarno_backend.core.config import AudioConfig

log = logging.getLogger(__name__)

# German Piper voice: Thorsten (medium quality, Creative Commons 0)
_DEFAULT_VOICE = "de_DE-thorsten-medium"


class PiperSynthesizer:
    """Converts text to speech using local Piper TTS and plays it."""

    def __init__(self, config: AudioConfig) -> None:
        self._language = config.language
        self._voice = _DEFAULT_VOICE
        self._mixer_ready = False

        try:
            from piper import PiperVoice
            from piper.download import get_voices
            self._piper_class = PiperVoice
            self._get_voices = get_voices
            self._model_path = self._ensure_model()
            self._voice = PiperVoice.load(self._model_path)
            log.info("TTS: Piper geladen (%s)", self._voice)
        except Exception:
            log.exception("Piper TTS konnte nicht geladen werden")
            raise

        try:
            pygame.mixer.init()
            self._mixer_ready = True
            log.info("Audio-Ausgabe initialisiert (pygame mixer)")
        except Exception:
            log.exception("pygame mixer konnte nicht initialisiert werden")

    def _ensure_model(self) -> Path:
        """Download or locate the Piper model using huggingface_hub."""
        from huggingface_hub import hf_hub_download

        model_dir = Path.home() / ".tarno" / "models" / "piper"
        model_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Lade die .onnx Modell-Datei
            model_path = Path(
                hf_hub_download(
                    repo_id="speaches-ai/piper-de_DE-thorsten-medium",
                    filename="model.onnx",
                    local_dir=str(model_dir),
                    local_dir_use_symlinks=False,
                )
            )
            # Lade die zugehörige .json Konfigurations-Datei
            hf_hub_download(
                repo_id="speaches-ai/piper-de_DE-thorsten-medium",
                filename="model.onnx.json",
                local_dir=str(model_dir),
                local_dir_use_symlinks=False,
            )
            return model_path
        except Exception:
            log.exception("Piper Modell konnte nicht beschafft werden")
            raise

    def speak(self, text: str) -> None:
        if not text:
            return
        log.info("TARNO: %s", text)
        if not self._mixer_ready:
            return

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            self._voice.synthesize(text, tmp_path)
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.05)
        except Exception:
            log.exception("Piper TTS Fehler")
        finally:
            pygame.mixer.music.unload()
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def stop(self) -> None:
        if self._mixer_ready:
            pygame.mixer.music.stop()
