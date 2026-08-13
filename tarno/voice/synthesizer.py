"""Text-to-speech output with local engines, streaming and fallback."""

from __future__ import annotations

import hashlib
import logging
import re
import tempfile
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pygame
import pyaudio

from tarno.voice.speech_naturalizer import SpeechNaturalizer
from tarno.voice.tts_engines import BaseTTSEngine, get_tts_engine
from tarno.voice.tts_engines.base import TTSAudioChunk
from tarno.voice.tts_output import TTSOutputStream

if TYPE_CHECKING:
    from tarno.core.config import AudioConfig

log = logging.getLogger(__name__)

# Default online voice used only by the edge-tts fallback.
_EDGE_VOICE = "de-DE-ConradNeural"

# See tarno/voice/audio_stream.py's identical constant/heuristic for the
# microphone side - same caveat: SDL2 exposes no reliable "is this built-in"
# flag, this is a best-effort name-pattern match only.
_BUILTIN_NAME_HINTS = ("array", "internal", "built-in", "eingebaut", "laptop", "intern")


def _is_builtin_device_name(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in _BUILTIN_NAME_HINTS)


def list_output_devices() -> list[dict]:
    """Enumerate playback devices for the Settings speaker picker, via
    pygame's SDL2 binding. Does not require an initialized mixer."""
    try:
        from pygame import _sdl2 as sdl2  # noqa: PLC0415 (optional subpackage, imported lazily)
    except Exception:
        log.warning("pygame._sdl2 nicht verfügbar - Lautsprecher-Liste leer")
        return []
    try:
        # SDL's audio subsystem must be initialized before device queries
        # work - safe/idempotent if pygame.mixer.init() already ran elsewhere.
        if not pygame.get_init():
            pygame.init()
        names = sdl2.audio.get_audio_device_names(False)  # False = playback devices
        return [
            {
                "index": i,
                "name": name,
                "is_default": False,  # SDL2 has no explicit "system default" marker in this enumeration
                "is_builtin": _is_builtin_device_name(name),
            }
            for i, name in enumerate(names)
        ]
    except Exception:
        log.exception("Lautsprecher-Geräteliste konnte nicht abgefragt werden")
        return []

# Fenstergroesse fuer die Amplituden-Huellkurve, die den Orb waehrend des
# Sprechens antreibt. 12ms loest einzelne Konsonanten-Attacks (Wortanfaenge)
# auf - mit den vorherigen 90ms verschmolzen Attacks komplett im Fenstermittel,
# der Orb wirkte wie ein traeger "spricht gerade"-Indikator statt einem
# Lautstaerke-Visualizer.
_ENVELOPE_WINDOW_MS = 12


def _compute_speech_envelope(audio_path: str) -> tuple[list[float], float]:
    """Real amplitude envelope of an already-synthesized audio file, used to
    drive the Orb's whole-body resonance in genuine sync with what TARNO is
    actually saying (not a procedural/rhythmic loop). Decodes via pygame's
    own Sound loader (no new dependency - pygame already handles the mp3
    cache files here) and computes RMS per fixed-size window, normalized
    against the loudest window in the clip."""
    try:
        sound = pygame.mixer.Sound(audio_path)
        duration = float(sound.get_length())
        raw = sound.get_raw()
        init = pygame.mixer.get_init()
        freq, size, channels = init if init else (44100, -16, 2)
        dtype = np.int16 if abs(size) == 16 else np.int8
        samples = np.frombuffer(raw, dtype=dtype).astype(np.float64)
        if channels > 1:
            samples = samples.reshape(-1, channels).mean(axis=1)
    except Exception:
        log.warning("Envelope-Berechnung fehlgeschlagen: %s", audio_path, exc_info=True)
        return [], 0.0

    window_samples = max(1, int(freq * _ENVELOPE_WINDOW_MS / 1000))
    levels: list[float] = []
    for start in range(0, len(samples), window_samples):
        chunk = samples[start:start + window_samples]
        if chunk.size == 0:
            continue
        levels.append(float(np.sqrt(np.mean(np.square(chunk)))))

    peak = max(levels) if levels else 0.0
    if peak > 0:
        levels = [min(1.0, level / peak) for level in levels]
    return levels, duration


def _sanitize_for_speech(text: str) -> str:
    """Strip markdown/formatting punctuation that an LLM uses to *mark up*
    text but that should never be read aloud verbatim — bold/italic stars,
    headers, code fences, links, tables, dotted acronyms, etc. The rule of
    thumb: anything that's there to change how text *looks* gets removed;
    anything that's part of the actual words stays."""

    # Fenced/inline code — drop code blocks entirely, unwrap inline code.
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Collapse dotted acronyms/spelled-out words (2+ single letters separated
    # by dots) into a plain run of letters: "J.A.R.V.I.S." -> "TARNO".
    text = re.sub(
        r"\b(?:[A-Za-zÄÖÜäöü]\.){2,}",
        lambda m: m.group(0).replace(".", ""),
        text,
    )

    # Emphasis: ***bold italic***, **bold**, *italic*, ___/__/_ variants, ~~strike~~.
    text = re.sub(r"\*{1,3}([^*]+?)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+?)_{1,3}", r"\1", text)
    text = re.sub(r"~~([^~]+)~~", r"\1", text)

    # Headers, blockquotes, horizontal rules, list bullets/numbers.
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*([-*_]\s*){3,}$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+[.)]\s+", "", text, flags=re.MULTILINE)

    # Links/images: [text](url), ![alt](url) -> just the text.
    text = re.sub(r"!?\[([^\]]*)\]\([^)]+\)", r"\1", text)

    # Table pipes and separator rows.
    text = re.sub(r"^\|?[\s:|-]+\|$", "", text, flags=re.MULTILINE)
    text = text.replace("|", " ")

    # Collapse repeated/mixed punctuation ("!!!", "??", "?!?!", "...") the
    # model sometimes uses for emphasis instead of tone.
    text = re.sub(r"[!?]{2,}", lambda m: m.group(0)[0], text)
    text = re.sub(r"\.{4,}", "...", text)

    # Leftover stray emphasis/heading characters and excess whitespace.
    text = re.sub(r"[*_~#]", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


class SpeechSynthesizer:
    """Converts text to speech and plays it through the speakers.

    Uses a chain of local TTS engines (NeuTTS, Piper, edge-tts) and supports
    real-time streaming as well as sentence/file fallback.
    """

    def __init__(
        self,
        config: AudioConfig,
        on_tts_started: "Callable[[str, list[float], float], None] | None" = None,
        on_tts_finished: "Callable[[], None] | None" = None,
    ) -> None:
        self._config = config
        self._language = config.language
        self._speed = config.speed
        self._rate = f"{int((self._speed - 1.0) * 100):+d}%"
        self._cache_dir = Path(config.tts_cache_dir).expanduser()
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        # KERNFIX (Live-Test, siehe tools/debug_proactive_live.py): speak()
        # haelt self._lock fuer den gesamten Aufruf und ruft im Datei-
        # Fallback-Pfad _speak_file() auf, das denselben Lock ERNEUT
        # acquired ("with self._lock:") - mit einem einfachen threading.Lock
        # ist das ein garantierter Selbst-Deadlock, reproduzierbar sobald der
        # Streaming-Pfad nicht greift (tts_streaming=False oder alle Engines
        # scheitern beim Streaming). RLock erlaubt reentrantes Acquire durch
        # denselben Thread und behebt das ohne die bestehende Kritische-
        # Sektion-Semantik an anderen with-self._lock-Stellen zu aendern.
        self._lock = threading.RLock()
        self._on_tts_started = on_tts_started
        self._on_tts_finished = on_tts_finished
        # None = SDL/OS default output device. Set via set_output_device().
        self._output_device: str | None = None
        self._output_device_index: int | None = None
        self._mixer_ready = False
        self._confirmation_sound: pygame.mixer.Sound | None = None
        self._engines: list[BaseTTSEngine] = []
        self._current_stream: TTSOutputStream | None = None
        self._naturalizer = SpeechNaturalizer(tts_prompt=config.tts_prompt)

        self._init_pygame()
        self._init_engines()

    def _init_pygame(self) -> None:
        try:
            pygame.mixer.init(devicename=self._output_device)
            self._mixer_ready = True
            log.info("Audio-Ausgabe initialisiert (pygame mixer)")
            try:
                self._confirmation_sound = pygame.mixer.Sound(
                    str(self._resolve_asset_path("confirmation.wav"))
                )
                log.info("Bestätigungston geladen")
            except Exception:
                log.warning("Bestätigungston konnte nicht geladen werden", exc_info=True)
        except Exception:
            log.exception("pygame mixer konnte nicht initialisiert werden")

    def _init_engines(self) -> None:
        tts_config = {
            "language": self._config.language,
            "voice": self._config.voice,
            "speed": self._config.speed,
            "voice_reference_path": getattr(self._config, "voice_reference_path", ""),
        }
        preferred = (self._config.tts_engine or "piper").lower()
        names = [preferred]
        if preferred != "piper":
            names.append("piper")
        if preferred != "edge-tts":
            names.append("edge-tts")

        for engine in self._engines:
            try:
                engine.close()
            except Exception:
                log.warning("TTS-Engine '%s' konnte nicht sauber geschlossen werden", engine.name, exc_info=True)
        self._engines.clear()
        for name in names:
            try:
                engine = get_tts_engine(name, tts_config)
                self._engines.append(engine)
                log.info("TTS-Engine verfügbar: %s", engine.name)
            except Exception:
                log.warning("TTS-Engine '%s' konnte nicht geladen werden", name, exc_info=True)

        if not self._engines:
            log.error("Keine TTS-Engine verfügbar")

        self._engine_signature = (
            self._config.language,
            self._config.voice,
            self._config.tts_engine,
        )

    def _ensure_engines(self) -> None:
        """Re-init engines if language/voice/tts_engine changed at runtime."""
        current = (self._config.language, self._config.voice, self._config.tts_engine)
        if getattr(self, "_engine_signature", None) != current:
            log.info("TTS-Engine-Signatur geändert: %s → %s", self._engine_signature, current)
            self._init_engines()

    def _cache_path(self, text: str, engine: BaseTTSEngine) -> Path:
        """Deterministic path for a TTS audio cache entry."""
        key = hashlib.sha256(f"{text}|{engine.name}|{self._rate}".encode("utf-8")).hexdigest()
        return self._cache_dir / f"{key}.wav"

    def speak(self, text: str) -> None:
        if not text:
            return

        with self._lock:
            self._stop_current_stream()
            self._reinit_mixer_if_needed()
            self._ensure_engines()

            spoken_text = _sanitize_for_speech(text)
            if not spoken_text:
                return
            spoken_text = self._naturalizer.enhance(spoken_text)
            log.info("TARNO: %s", spoken_text)

            if self._config.tts_streaming:
                for engine in self._engines:
                    if not engine.supports_streaming:
                        continue
                    try:
                        if self._speak_streaming(spoken_text, engine):
                            return
                    except Exception:
                        log.exception("TTS-Streaming mit %s fehlgeschlagen", engine.name)
                        self._stop_current_stream()

            # Fallback or non-streaming path: synthesize a file and play it.
            for engine in self._engines:
                try:
                    if self._speak_file(spoken_text, engine):
                        return
                except Exception:
                    log.exception("TTS-Datei-Ausgabe mit %s fehlgeschlagen", engine.name)

            log.error("TTS vollständig fehlgeschlagen für: %s", spoken_text)

    def _reinit_mixer_if_needed(self) -> None:
        """Ensure the pygame mixer is alive; required for confirmations/fallback."""
        if pygame.mixer.get_init() is None:
            try:
                pygame.mixer.init(devicename=self._output_device)
                self._mixer_ready = True
            except Exception:
                log.exception("pygame mixer konnte nicht initialisiert werden")
                self._mixer_ready = False

    def _speak_streaming(self, text: str, engine: BaseTTSEngine) -> bool:
        """Play text using a real-time output stream."""
        try:
            stream = TTSOutputStream(
                sample_rate=engine.sample_rate,
                sample_width=engine.sample_width,
                num_channels=engine.num_channels,
                device_index=self._output_device_index,
            )
        except Exception:
            log.exception("TTS-Ausgabestream konnte nicht geöffnet werden")
            return False

        self._current_stream = stream
        first_chunk_event = threading.Event()
        first_chunk: list[TTSAudioChunk | None] = [None]
        error_occurred: list[bool] = [False]

        def _synth() -> None:
            try:
                for chunk in engine.synthesize_stream(text):
                    if first_chunk[0] is None:
                        first_chunk[0] = chunk
                        first_chunk_event.set()
                    stream.write(chunk)
            except Exception:
                log.exception("TTS-Synthese-Thread Fehler")
                error_occurred[0] = True
                first_chunk_event.set()
            finally:
                stream.finish()

        thread = threading.Thread(target=_synth, daemon=True, name=f"TTSSynthesis-{engine.name}")
        thread.start()

        timeout = getattr(self._config, "tts_stream_timeout_sec", 2.0)
        if not first_chunk_event.wait(timeout=timeout):
            log.warning(
                "TTS-Timeout für ersten Audio-Chunk nach %.1fs mit %s",
                timeout,
                engine.name,
            )
            stream.stop()
            stream.close()
            return False

        if error_occurred[0] or first_chunk[0] is None:
            stream.stop()
            stream.close()
            return False

        if self._on_tts_started is not None:
            # Streaming has no final envelope yet; pass empty envelope.
            self._on_tts_started(text, [], 0.0)

        stream.wait_until_done()
        if self._on_tts_finished is not None:
            self._on_tts_finished()
        return True

    def _speak_file(self, text: str, engine: BaseTTSEngine) -> bool:
        """Synthesize to a file and play it back with pygame."""
        cache_path = self._cache_path(text, engine)
        if not cache_path.exists() or cache_path.stat().st_size == 0:
            if not engine.synthesize_to_file(text, cache_path):
                return False

        if not cache_path.exists() or cache_path.stat().st_size == 0:
            return False

        with self._lock:
            if not self._mixer_ready or pygame.mixer.get_init() is None:
                self._reinit_mixer_if_needed()
                if not self._mixer_ready:
                    return False

            try:
                envelope, duration = [], 0.0
                if self._on_tts_started is not None:
                    envelope, duration = _compute_speech_envelope(str(cache_path))
                    log.info("TTS Envelope berechnet: %d samples, %.3fs", len(envelope), duration)

                pygame.mixer.music.load(str(cache_path))
                pygame.mixer.music.play()
                log.info("TTS play() gestartet für: %s", text[:60])

                if self._on_tts_started is not None:
                    self._on_tts_started(text, envelope, duration)

                max_wait = max(10.0, len(text) / 8.0)
                waited = 0.0
                while pygame.mixer.music.get_busy():
                    if waited >= max_wait:
                        log.warning(
                            "TTS-Wiedergabe nach %.0fs nicht beendet (get_busy() blieb True) - breche ab",
                            max_wait,
                        )
                        break
                    time.sleep(0.05)
                    waited += 0.05
            except Exception:
                log.exception("TTS-Fehler")
                return False
            finally:
                try:
                    pygame.mixer.music.stop()
                except Exception:
                    pass
                pygame.mixer.music.unload()
                if self._on_tts_finished is not None:
                    self._on_tts_finished()
        return True

    def _resolve_output_device(self, name: str | None) -> int | None:
        """Map an output device name to a PortAudio index."""
        if name is None or str(name).lower() in ("default", "standard", "", "none"):
            return None
        pa = pyaudio.PyAudio()
        try:
            target = str(name).lower()
            for i in range(pa.get_device_count()):
                info = pa.get_device_info_by_index(i)
                if info.get("maxOutputChannels", 0) <= 0:
                    continue
                dev_name = str(info.get("name", "")).lower()
                if target in dev_name or dev_name in target:
                    return i
            log.warning("Ausgabegerät '%s' nicht gefunden - verwende Standard", name)
            return None
        finally:
            pa.terminate()

    def _stop_current_stream(self) -> None:
        if self._current_stream is not None:
            try:
                self._current_stream.stop()
                self._current_stream.close()
            except Exception:
                log.exception("Fehler beim Stoppen des TTS-Streams")
            self._current_stream = None

    def stop(self) -> None:
        with self._lock:
            self._stop_current_stream()
            if self._mixer_ready and pygame.mixer.get_init() is not None:
                pygame.mixer.music.stop()
                pygame.mixer.stop()

    def play_sound(self) -> None:
        """Play a short confirmation sound on a pygame mixer channel.

        This is intentionally non-blocking: the caller should start listening
        immediately so the user can continue speaking without waiting.
        """
        if self._confirmation_sound is None:
            log.warning("Kein Bestätigungston verfügbar")
            return

        with self._lock:
            self._reinit_mixer_if_needed()
            if not self._mixer_ready:
                return

            try:
                self._confirmation_sound.set_volume(0.3)
                self._confirmation_sound.play()
            except Exception:
                log.exception("Bestätigungston-Fehler")

    def set_output_device(self, device: str | None) -> bool:
        """Switch TTS playback to a different output device."""
        normalized = None if device is None or str(device).lower() in ("default", "standard", "") else device
        with self._lock:
            try:
                self._stop_current_stream()
                if pygame.mixer.get_init() is not None:
                    pygame.mixer.quit()
                pygame.mixer.init(devicename=normalized)
                self._mixer_ready = True
                self._output_device = normalized
                self._output_device_index = self._resolve_output_device(normalized)

                try:
                    self._confirmation_sound = pygame.mixer.Sound(
                        str(self._resolve_asset_path("confirmation.wav"))
                    )
                except Exception:
                    log.warning("Bestätigungston nach Geräte-Wechsel nicht neu geladen", exc_info=True)
                log.info("Audio-Ausgabegerät gewechselt zu: %s", normalized or "Standard")
                return True
            except Exception:
                log.exception("Audio-Ausgabegerät konnte nicht gewechselt werden: %s", device)
                self._mixer_ready = False
                return False

    @staticmethod
    def _resolve_asset_path(name: str) -> Path:
        """Return a resource path that works in source and PyInstaller builds."""
        # In PyInstaller one-dir builds the module lives under _internal/tarno/voice,
        # so two parents up is _internal/tarno — exactly where the asset is bundled.
        root = Path(__file__).resolve().parent.parent
        return root / "assets" / name
