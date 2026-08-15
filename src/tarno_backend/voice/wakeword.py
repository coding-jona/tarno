"""Wake word detection using Vosk, openWakeWord, or pvporcupine."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
import zipfile
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import numpy as np

from tarno_backend.voice.audio_utils import AutomaticGainControl

if TYPE_CHECKING:
    from tarno_backend.core.config import AGCConfig, WakeWordConfig

log = logging.getLogger(__name__)

_OPENWAKEWORD_MODELS_DIR = Path.home() / ".tarno" / "models" / "openwakeword"

# Bundled model filenames inside openwakeword/resources/models.
# Fallback to hey_jarvis if the user selects an unsupported model name.
_OWW_MODEL_MAP = {
    "hey_jarvis": "hey_jarvis_v0.1.onnx",
    "jarvis": "hey_jarvis_v0.1.onnx",
    "jarvis_v1": "hey_jarvis_v0.1.onnx",
    "hey_mycroft": "hey_mycroft_v0.1.onnx",
    "alexa": "alexa_v0.1.onnx",
    "timer": "timer_v0.1.onnx",
    "weather": "weather_v0.1.onnx",
}

_VOSK_MODELS_DIR = Path.home() / ".tarno" / "models"

# name -> (folder name after unzip, download URL). Confirmed against
# alphacephei.com/vosk/models - small has a closed lexicon that drops
# unlisted words (e.g. "tarno") from the grammar entirely at compile time
# (verified live: "Ignoring word missing in vocabulary" for javis/tarno/
# tano/taano), large has broader coverage. User-selectable via Settings
# (WakeWordConfig.vosk_model_size), lazily downloaded on first selection.
_VOSK_MODELS: dict[str, tuple[str, str]] = {
    "small": ("vosk-model-small-de-0.15", "https://alphacephei.com/vosk/models/vosk-model-small-de-0.15.zip"),
    "large": ("vosk-model-de-0.21", "https://alphacephei.com/vosk/models/vosk-model-de-0.21.zip"),
}

# English pronunciation of "Jarvis" (the common case - it's an English name,
# most speakers say it the English way even mid-German-sentence) doesn't
# reliably match the German model's acoustic model, even though "jarvis" is
# in its lexicon - found live: German-model-only setup missed English
# pronunciation. Run a small English grammar-capable model alongside the
# German one instead of trying to pick one language.
_VOSK_EN_MODEL_NAME = "vosk-model-small-en-us-0.15"
_VOSK_EN_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"

_VOSK_DOWNLOAD_RETRIES = 5
_VOSK_SAMPLE_RATE = 16000  # matches AudioConfig.sample_rate (hardcoded throughout the pipeline)


def _download_vosk_model(name: str, url: str, progress_cb: Callable[[int], None] | None = None) -> Path:
    """Lazily download + extract a Vosk model, resuming on transient
    connection drops (found live: large 1.9GB downloads on flaky networks
    stall partway through and need several resumed retries to complete)."""
    target_dir = _VOSK_MODELS_DIR / name
    if target_dir.exists():
        return target_dir

    _VOSK_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = _VOSK_MODELS_DIR / f"{name}.zip"
    log.info("Lade Vosk-Modell '%s' herunter: %s", name, url)

    last_error: Exception | None = None
    for attempt in range(1, _VOSK_DOWNLOAD_RETRIES + 1):
        existing = zip_path.stat().st_size if zip_path.exists() else 0
        headers = {"Range": f"bytes={existing}-"} if existing else {}
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                content_range = resp.headers.get("Content-Range", "")
                total = existing + int(resp.headers.get("Content-Length", 0) or 0)
                if "/" in content_range:
                    total = int(content_range.rsplit("/", 1)[-1])
                mode = "ab" if existing and resp.status == 206 else "wb"
                downloaded = existing if mode == "ab" else 0
                with zip_path.open(mode) as f:
                    while True:
                        chunk = resp.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb and total:
                            progress_cb(min(100, int(downloaded * 100 / total)))
            if zip_path.stat().st_size >= total > 0:
                last_error = None
                break
            last_error = RuntimeError(
                f"Download unvollständig: {zip_path.stat().st_size}/{total} Bytes"
            )
        except (urllib.error.URLError, OSError, RuntimeError) as exc:
            last_error = exc
            log.warning(
                "Vosk-Modell-Download unterbrochen (Versuch %d/%d): %s",
                attempt, _VOSK_DOWNLOAD_RETRIES, exc,
            )
            time.sleep(min(2 * attempt, 10))

    if last_error is not None:
        zip_path.unlink(missing_ok=True)
        raise RuntimeError(f"Vosk-Modell '{name}' konnte nicht heruntergeladen werden") from last_error

    log.info("Entpacke Vosk-Modell '%s'...", name)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(str(_VOSK_MODELS_DIR))
    zip_path.unlink(missing_ok=True)
    log.info("Vosk-Modell '%s' bereit unter %s", name, target_dir)
    return target_dir


class WakeWordDetector:
    """Always-on wake word detection."""

    def __init__(self, config: WakeWordConfig, agc_config: "AGCConfig | None" = None) -> None:
        """Try to initialize the requested backend first, then fall back
        through the others (vosk -> openwakeword -> porcupine order) until
        one actually loads. Raises only if every backend fails."""
        self._threshold = config.threshold
        self._patience = max(1, config.patience)
        self._debounce_time = config.debounce_time
        self._consecutive = 0
        self._last_trigger = 0.0
        self._model_key = config.model_name
        self._backend: str = "openwakeword"
        if agc_config is None:
            from tarno_backend.core.config import AGCConfig
            agc_config = AGCConfig()
        self._agc_enabled = agc_config.enabled
        self._agc = AutomaticGainControl(agc_config)
        self._wake_phrases = list(config.wake_phrases)
        self._vosk_model_size = config.vosk_model_size

        # Robust fallback chain: requested backend first, then the best
        # alternative. Default is Vosk (local, no API key); openWakeWord is the
        # bundled fallback; porcupine needs a key and is tried last.
        preferred_order: list[tuple[str, Callable[[WakeWordConfig], None]]] = [
            ("vosk", self._init_vosk),
            ("openwakeword", self._init_openwakeword),
            ("porcupine", self._init_porcupine),
        ]
        requested = config.backend
        order = [entry for entry in preferred_order if entry[0] == requested] + [
            entry for entry in preferred_order if entry[0] != requested
        ]

        last_error: Exception | None = None
        for name, init in order:
            try:
                init(config)
                self._backend = name
                if name in {"porcupine", "vosk"}:
                    self._patience = 1
                log.info("Wake-Word-Backend aktiviert: %s", name)
                return
            except Exception as exc:
                last_error = exc
                log.warning("Wake-Word-Backend %s nicht verfügbar: %s", name, exc)

        if last_error is not None:
            raise last_error
        raise RuntimeError("Kein Wake-Word-Backend verfügbar")

    def _init_vosk(self, config: WakeWordConfig) -> None:
        """Load the German (and, alongside it, a fixed small English) Vosk
        model, downloading either one on first use. Raises on any failure -
        the caller's fallback chain decides what happens next."""
        try:
            import vosk

            vosk.SetLogLevel(-1)  # Vosk is very chatty on stderr by default

            de_name, de_url = _VOSK_MODELS.get(config.vosk_model_size, _VOSK_MODELS["small"])
            model_dir = _download_vosk_model(de_name, de_url)
            self._vosk_model = vosk.Model(str(model_dir))
            # Hardcoded like openWakeWord's own internal assumption below -
            # AudioConfig.sample_rate is 16000 everywhere in this codebase
            # (WakeWordConfig itself carries no sample-rate field to pass in).
            self._vosk_recognizer = self._make_vosk_recognizer(self._vosk_model, _VOSK_SAMPLE_RATE)

            # English recognizer runs alongside the German one on every
            # frame (see _process_vosk) - "Jarvis" is usually said the
            # English way even by German speakers, and that pronunciation
            # doesn't reliably match the German acoustic model even though
            # "jarvis" is technically in its lexicon.
            en_dir = _download_vosk_model(_VOSK_EN_MODEL_NAME, _VOSK_EN_MODEL_URL)
            self._vosk_model_en = vosk.Model(str(en_dir))
            self._vosk_recognizer_en = self._make_vosk_recognizer(self._vosk_model_en, _VOSK_SAMPLE_RATE)

            # DEBUG-only, ungrammared ("free decode") recognizers - grammar
            # mode always snaps to the closest in-vocabulary word or "[unk]",
            # so a near-miss (e.g. an accented pronunciation) gives zero
            # insight into what Vosk actually heard. These run the same audio
            # through each model with no vocabulary restriction so failed
            # attempts show up in the log as real (if imperfect) transcribed
            # text - the fastest way to find the exact spelling to add to
            # wake_phrases for a pronunciation that doesn't yet match.
            self._vosk_debug_enabled = log.isEnabledFor(logging.DEBUG)
            if self._vosk_debug_enabled:
                self._vosk_debug_recognizer = vosk.KaldiRecognizer(self._vosk_model, _VOSK_SAMPLE_RATE)
                self._vosk_debug_recognizer_en = vosk.KaldiRecognizer(self._vosk_model_en, _VOSK_SAMPLE_RATE)

            log.info(
                "Wake-Word-Modell 'vosk-model-%s-de' + '%s' geladen, Vokabular=%s",
                config.vosk_model_size,
                _VOSK_EN_MODEL_NAME,
                self._wake_phrases,
            )
        except Exception:
            log.exception("Vosk Wake-Word-Modell konnte nicht geladen werden")
            raise

    def _make_vosk_recognizer(self, model, sample_rate: int):
        """Build a grammar-constrained recognizer that can only ever output
        one of our wake_phrases or "[unk]" - see _match_vosk_recognizer."""
        import vosk

        grammar = json.dumps(self._wake_phrases + ["[unk]"])
        return vosk.KaldiRecognizer(model, sample_rate, grammar)

    def set_vosk_model_size(self, model_size: str, sample_rate: int = _VOSK_SAMPLE_RATE) -> None:
        """Hot-swap the loaded German Vosk model (Settings small/large
        toggle) without rebuilding the whole WakeWordDetector/VoiceController.
        Only valid while backend == "vosk"; the English recognizer is
        unaffected (it always uses its own fixed small model). Explicitly
        drops the old model reference and forces a GC pass before loading the
        new one - the large German model is a big native allocation, and
        relying on GC timing alone would let both models sit in memory
        simultaneously for an unpredictable while."""
        if self._backend != "vosk":
            return
        if model_size == self._vosk_model_size:
            return
        import gc

        log.info("Wechsle Vosk-Modell: %s -> %s", self._vosk_model_size, model_size)
        import vosk

        name, url = _VOSK_MODELS.get(model_size, _VOSK_MODELS["small"])
        model_dir = _download_vosk_model(name, url)
        old_model = self._vosk_model
        self._vosk_model = vosk.Model(str(model_dir))
        self._vosk_recognizer = self._make_vosk_recognizer(self._vosk_model, sample_rate)
        self._vosk_model_size = model_size
        del old_model
        gc.collect()
        log.info("Vosk-Modell gewechselt: %s aktiv", model_size)

    def _init_porcupine(self, config: WakeWordConfig) -> None:
        """Load a Picovoice Porcupine model. Requires an access key (env
        var or config); raises immediately if none is set, since there's
        no local fallback for that."""
        try:
            import pvporcupine

            access_key = os.environ.get("PICOVOICE_API_KEY", "")
            if not access_key:
                access_key = getattr(config, "picovoice_access_key", "") or ""
            if not access_key:
                raise RuntimeError(
                    "PICOVOICE_API_KEY (oder wakeword.picovoice_access_key) ist nicht gesetzt. "
                    "Picovoice erfordert einen Access Key (https://console.picovoice.ai/)."
                )

            keyword = config.model_name or "jarvis"
            self._porcupine = pvporcupine.create(
                access_key=access_key,
                keywords=[keyword],
                sensitivities=[float(config.sensitivity)],
            )
            self._frame_length = self._porcupine.frame_length
            self._buffer: deque[int] = deque()
            log.info(
                "Wake-Word-Modell '%s' (pvporcupine) geladen, frame_length=%d",
                keyword,
                self._frame_length,
            )
        except Exception:
            log.exception("pvporcupine Wake-Word-Modell konnte nicht geladen werden")
            raise

    def _init_openwakeword(self, config: WakeWordConfig) -> None:
        """Load an openWakeWord model, downloading its (never PyPI-bundled)
        weight files on first use. See the KERNFIX comment below for why
        that download step exists at all."""
        try:
            from openwakeword.model import Model as OWWModel

            models_dir = _OPENWAKEWORD_MODELS_DIR
            ext = "onnx" if config.inference_framework == "onnx" else "tflite"
            melspec_path = models_dir / f"melspectrogram.{ext}"
            embedding_path = models_dir / f"embedding_model.{ext}"

            normalized = config.model_name.replace(" ", "_").lower()
            model_filename = _OWW_MODEL_MAP.get(normalized)
            if model_filename is None:
                log.warning(
                    "Unbekanntes Wake-Word '%s'; verwende hey_jarvis", config.model_name
                )
                model_filename = "hey_jarvis_v0.1.onnx"
            wakeword_path = models_dir / model_filename

            # KERNFIX: die Modell-Dateien (.onnx/.tflite, mehrere MB) sind nie
            # Teil des openwakeword-PyPI-Pakets - dieses vendored bisher einen
            # lokalen Pfad, der weder im Quellbaum noch im gepackten Build je
            # existierte, sodass dieses Backend immer sofort mit
            # FileNotFoundError fehlschlug. Genau wie die Vosk-Modelle
            # (_download_vosk_model) werden sie jetzt bei Bedarf einmalig
            # nach ~/.tarno/models/openwakeword heruntergeladen, ueber die
            # offizielle Download-Funktion des Pakets selbst (kennt die
            # jeweils aktuellen Release-URLs, muessen hier nicht dupliziert
            # werden).
            if not (wakeword_path.exists() and melspec_path.exists() and embedding_path.exists()):
                from openwakeword.utils import download_models as _download_oww_models

                models_dir.mkdir(parents=True, exist_ok=True)
                log.info("Lade openWakeWord-Modell '%s' herunter...", model_filename)
                _download_oww_models(
                    model_names=[os.path.splitext(model_filename)[0]],
                    target_directory=str(models_dir),
                )

            if not wakeword_path.exists():
                raise FileNotFoundError(f"Wake-Word-Modell nicht gefunden: {wakeword_path}")
            if not melspec_path.exists():
                raise FileNotFoundError(f"Melspec-Modell nicht gefunden: {melspec_path}")
            if not embedding_path.exists():
                raise FileNotFoundError(f"Embedding-Modell nicht gefunden: {embedding_path}")

            self._model = OWWModel(
                wakeword_models=[str(wakeword_path)],
                inference_framework=config.inference_framework,
                melspec_model_path=str(melspec_path),
                embedding_model_path=str(embedding_path),
            )
            self._model_key = os.path.splitext(model_filename)[0]
            log.info("Wake-Word-Modell '%s' geladen (openWakeWord)", self._model_key)
        except Exception:
            log.exception("openWakeWord Modell konnte nicht geladen werden")
            raise

    def process_frame(self, audio_chunk: np.ndarray) -> bool:
        """Feed one audio chunk to the active backend. Returns True exactly
        once per real wake-word detection (debounced/patience-gated inside
        each backend's _process_* method)."""
        if self._backend == "vosk":
            return self._process_vosk(audio_chunk)
        if self._backend == "porcupine":
            return self._process_porcupine(audio_chunk)
        return self._process_openwakeword(audio_chunk)

    def _match_vosk_recognizer(self, rec, audio_bytes: bytes) -> str | None:
        """Feed audio to one grammar-constrained recognizer and return the
        matched wake phrase, or None if it heard "[unk]"/nothing."""
        wake_phrases = self._wake_phrases
        if rec.AcceptWaveform(audio_bytes):
            result = json.loads(rec.Result())
            text = result.get("text", "").strip().lower()
        else:
            partial = json.loads(rec.PartialResult())
            text = partial.get("partial", "").strip().lower()
        # Grammar mode only ever yields one of our listed phrases or "[unk]" -
        # exact membership is enough, no fuzzy matching needed.
        return text if text in wake_phrases else None

    def _log_vosk_free_decode(self, audio_bytes: bytes) -> None:
        """DEBUG-only: log what each model hears with no vocabulary
        restriction, so a mismatched accent shows up as real transcribed
        text instead of a silent non-match - use this output to find the
        exact spelling to add to wake_phrases."""
        for label, rec in (("de", self._vosk_debug_recognizer), ("en", self._vosk_debug_recognizer_en)):
            if rec.AcceptWaveform(audio_bytes):
                text = json.loads(rec.Result()).get("text", "").strip()
            else:
                text = json.loads(rec.PartialResult()).get("partial", "").strip()
            if text:
                log.debug("Vosk frei erkannt (%s, unbeschränktes Vokabular): '%s'", label, text)

    def _process_vosk(self, audio_chunk: np.ndarray) -> bool:
        """Vosk backend: run both language recognizers, debounce, and
        report a detection at most once per debounce window."""
        if self._agc_enabled:
            audio_chunk = self._agc.apply(audio_chunk)
        audio_bytes = audio_chunk.tobytes()

        # Run the German and English recognizers in parallel on the same
        # frame - "Jarvis" is usually said the English way even mid-German-
        # sentence, and that pronunciation doesn't reliably match the German
        # acoustic model even though the word itself is in its lexicon.
        detected_text = self._match_vosk_recognizer(self._vosk_recognizer, audio_bytes)
        detected_lang = "de"
        if detected_text is None:
            detected_text = self._match_vosk_recognizer(self._vosk_recognizer_en, audio_bytes)
            detected_lang = "en"

        if self._vosk_debug_enabled:
            self._log_vosk_free_decode(audio_bytes)

        if detected_text is None:
            return False

        now = time.monotonic()
        if now - self._last_trigger < self._debounce_time:
            log.debug(
                "Wake-Word Debounce aktiv (%.2fs verbleibend)",
                self._debounce_time - (now - self._last_trigger),
            )
            self._vosk_recognizer.Reset()
            self._vosk_recognizer_en.Reset()
            return False

        log.info("Wake word erkannt (vosk/%s): '%s'", detected_lang, detected_text)
        self._last_trigger = now
        self._vosk_recognizer.Reset()
        self._vosk_recognizer_en.Reset()
        return True

    def _process_porcupine(self, audio_chunk: np.ndarray) -> bool:
        """Porcupine backend: buffer audio into fixed-size frames (Porcupine
        needs exact frame_length chunks), run detection, apply
        patience/debounce."""
        if self._agc_enabled:
            audio_chunk = self._agc.apply(audio_chunk)
        self._buffer.extend(audio_chunk.tolist())
        detected = False
        while len(self._buffer) >= self._frame_length:
            frame = [self._buffer.popleft() for _ in range(self._frame_length)]
            result = self._porcupine.process(frame)
            if result >= 0:
                detected = True
                break

        if not detected:
            self._consecutive = 0
            return False

        self._consecutive += 1
        if self._consecutive < self._patience:
            return False

        now = time.monotonic()
        if now - self._last_trigger < self._debounce_time:
            return False

        log.debug("Wake word 'jarvis' erkannt")
        self._last_trigger = now
        self._consecutive = 0
        return True

    def _process_openwakeword(self, audio_chunk: np.ndarray) -> bool:
        """openWakeWord backend: score the chunk, require `patience`
        consecutive above-threshold frames, then debounce."""
        if self._agc_enabled:
            audio_chunk = self._agc.apply(audio_chunk)
        prediction = self._model.predict(audio_chunk)
        score = prediction.get(self._model_key, 0.0)

        self._consecutive = self._consecutive + 1 if score >= self._threshold else 0
        if self._consecutive < self._patience:
            if self._consecutive > 0:
                log.debug(
                    "Wake-Word Score=%.3f (unter Threshold=%.3f), patience=%d/%d",
                    score,
                    self._threshold,
                    self._consecutive,
                    self._patience,
                )
            return False

        now = time.monotonic()
        if now - self._last_trigger < self._debounce_time:
            log.debug(
                "Wake-Word Debounce aktiv (%.2fs verbleibend)",
                self._debounce_time - (now - self._last_trigger),
            )
            return False

        log.info("Wake word erkannt (score=%.3f, patience=%d)", score, self._consecutive)
        self._last_trigger = now
        self._consecutive = 0
        return True

    def reset(self) -> None:
        """Clear all detection state (patience counter, AGC, recognizer
        buffers) - call after a query completes so the next wake-word
        listen starts fresh."""
        log.debug("Wake-Word-Detector zurückgesetzt (backend=%s)", self._backend)
        self._consecutive = 0
        self._agc.reset()
        if self._backend == "vosk":
            self._vosk_recognizer.Reset()
            self._vosk_recognizer_en.Reset()
            if self._vosk_debug_enabled:
                self._vosk_debug_recognizer.Reset()
                self._vosk_debug_recognizer_en.Reset()
            return
        if self._backend == "porcupine":
            self._buffer.clear()
            return
        self._model.reset()
