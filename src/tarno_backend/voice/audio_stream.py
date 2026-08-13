"""Raw microphone audio stream for wake word detection and STT.

The stream supports a lightweight pause/resume cycle that keeps the PyAudio
instance alive. Only the full stop() destroys the PyAudio handle.
"""

from __future__ import annotations

import audioop
import logging
import math
import threading
import time
from typing import TYPE_CHECKING

import numpy as np
import pyaudio
import speech_recognition as sr

if TYPE_CHECKING:
    from tarno_backend.core.config import AudioConfig

log = logging.getLogger(__name__)

_FORMAT = pyaudio.paInt16

# Best-effort only - PortAudio/WASAPI expose no reliable "is this a built-in
# device" flag, so this is a heuristic name match against common built-in
# laptop microphone/speaker naming patterns (e.g. "Microphone Array (Realtek
# (R) Audio)" - notably also long enough to hit the MME 31-char truncation
# _find_device_index already guards against). Anything not matching is
# labeled "Extern" - wrong in either direction is just a cosmetic UI label,
# not a functional issue.
_BUILTIN_NAME_HINTS = ("array", "internal", "built-in", "eingebaut", "laptop", "intern")


def _is_builtin_device_name(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in _BUILTIN_NAME_HINTS)


def list_input_devices() -> list[dict]:
    """Enumerate all input-capable PortAudio devices for the Settings
    microphone picker. Doesn't require a running AudioStream - opens and
    closes its own short-lived PyAudio instance."""
    pa = pyaudio.PyAudio()
    try:
        default_index = AudioStream._resolve_default_input_device_static(pa)
        devices = []
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) <= 0:
                continue
            name = str(info.get("name", ""))
            try:
                host_api_name = str(pa.get_host_api_info_by_index(info["hostApi"])["name"])
            except Exception:
                host_api_name = "?"
            devices.append({
                "index": i,
                "name": name,
                "host_api": host_api_name,
                "is_default": i == default_index,
                "is_builtin": _is_builtin_device_name(name),
            })
        return devices
    finally:
        pa.terminate()


class AudioStream:
    """Manages a PyAudio input stream for continuous audio capture.

    Lifecycle:
        start()   — creates PyAudio + opens stream
        pause()   — stops the PortAudio stream but keeps PyAudio alive
        resume()  — re-opens the PortAudio stream on the same PyAudio instance
        stop()    — destroys everything (use only on shutdown)
    """

    _MAX_RESTART_ATTEMPTS = 3
    _RESTART_BACKOFF = 0.5  # seconds between restart attempts

    def __init__(self, config: AudioConfig) -> None:
        self._rate = config.sample_rate
        self._channels = config.channels
        self._chunk = config.chunk_size
        self._sample_width = pyaudio.get_sample_size(_FORMAT)
        self._lock = threading.Lock()
        self._pa: pyaudio.PyAudio | None = None
        self._stream: pyaudio.Stream | None = None
        self._started = False
        self._paused = False

        # Initialisiere Geräte-Index basierend auf Config (Name oder Index)
        self._device_index: int | None = self._find_device_index(config.microphone_device)

        # Manche WASAPI-Treiber (live beobachtet: Windows-10-Laptop, Realtek/
        # Conexant-Stack) lehnen das Oeffnen mit der konfigurierten Rate
        # (self._rate, i.d.R. 16000 Hz) mit "Invalid sample rate" (errno
        # -9997) ab und akzeptieren nur ihre native Mix-Rate (meist 48000 Hz)
        # im Shared Mode. _open_device_locked faengt das ab und oeffnet
        # dasselbe Geraet stattdessen mit seiner nativen Rate - read_frames()
        # resampled dann per audioop auf self._rate zurueck, sodass jeder
        # Aufrufer (Wakeword/AdaptiveListener/Whisper) weiterhin exakt die
        # konfigurierte Chunk-Groesse bei self._rate Hz sieht. Kein Resampling
        # noetig, wenn _capture_rate == self._rate (Normalfall).
        self._capture_rate: int = self._rate
        self._resample_state = None

    def _find_device_index(self, target: str | int) -> int | None:
        """Findet den PortAudio Index für einen Namen oder direkten Index."""
        if target is None or str(target).lower() in ("default", "standard", "-1", ""):
            return self._resolve_default_input_device()

        try:
            return int(target)
        except (ValueError, TypeError):
            pass

        # Namenssuche (fehlertolerant fuer die MME-API 31-Zeichen-Kuerzung -
        # ein API-Layer-Limit, identisch auf jeder Windows-Version, nicht
        # OS-versionsabhaengig). Baut auch bei gekuerzten Namen (z.B. lange
        # eingebaute Array-Mikrofonnamen wie "Microphone Array (Realtek(R)
        # Audio)") oft mehrere Treffer ueber verschiedene Host-APIs fuer
        # dasselbe physische Geraet auf (MME/DirectSound/WASAPI/WDM-KS) -
        # WASAPI-Treffer werden bevorzugt, da MME/DirectSound-Eintraege fuer
        # dasselbe Geraet oft schlechtere Latenz/Qualitaet liefern.
        pa = pyaudio.PyAudio()
        try:
            target_str = str(target).lower()
            wasapi_match: int | None = None
            other_match: int | None = None
            for i in range(pa.get_device_count()):
                info = pa.get_device_info_by_index(i)
                if info.get("maxInputChannels", 0) <= 0:
                    continue
                name = str(info.get("name", "")).lower()
                truncated_name = name[:31]
                if not (target_str in name or name in target_str or target_str.startswith(truncated_name)):
                    continue
                is_wasapi = self._is_wasapi_device(pa, info)
                if is_wasapi and wasapi_match is None:
                    wasapi_match = i
                elif not is_wasapi and other_match is None:
                    other_match = i
            if wasapi_match is not None:
                return wasapi_match
            return other_match
        finally:
            pa.terminate()

    @staticmethod
    def _is_wasapi_device(pa: pyaudio.PyAudio, device_info: dict) -> bool:
        try:
            return pa.get_host_api_info_by_index(device_info["hostApi"])["type"] == pyaudio.paWASAPI
        except Exception:
            return False

    def _resolve_default_input_device(self) -> int | None:
        pa = pyaudio.PyAudio()
        try:
            return self._resolve_default_input_device_static(pa)
        finally:
            pa.terminate()

    @staticmethod
    def _resolve_default_input_device_static(pa: pyaudio.PyAudio) -> int | None:
        """Löst das Windows-WASAPI-Standard-Eingabegerät auf, statt die
        Geräteauswahl PortAudios eigenem (host-API-abhängigem, i.d.R.
        WMME-basiertem) Standardgerät zu überlassen.

        Gefunden via Live-Test: ohne explizite WASAPI-Bindung kann PortAudios
        ambientes "Standardgerät" vom echten Windows-Standard-Gerät abweichen.
        Recherchiert (nicht geraten): dies ist KEIN Windows-10-vs-11-Unter-
        schied - beide nutzen denselben WASAPI/MME-Stack - sondern schlicht
        eine host-API-Diskrepanz zwischen PortAudios eigenem Default und dem
        von Windows selbst gemeldeten. Gibt None zurück, wenn WASAPI nicht
        verfügbar ist (Nicht-Windows-Systeme, oder PortAudio ohne WASAPI-
        Unterstützung gebaut) - der Aufrufer fällt dann auf PortAudios
        ambientes Standardgerät zurück (unverändertes Verhalten).
        """
        try:
            wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        except Exception:
            log.debug("WASAPI Host-API nicht verfügbar; verwende PortAudio-Standardgerät")
            return None

        default_index = wasapi_info.get("defaultInputDevice", -1)
        if not isinstance(default_index, int) or default_index < 0:
            log.debug("WASAPI liefert kein Standard-Eingabegerät; verwende PortAudio-Standardgerät")
            return None

        log.info("Nutze WASAPI-Standard-Eingabegerät (Index %d)", default_index)
        return int(default_index)

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._started and not self._paused

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._pa = pyaudio.PyAudio()
            self._open_stream_locked()
            self._started = True
            self._paused = False
        log.info("Audio stream gestartet (%d Hz, %d ch)", self._rate, self._channels)
        self._ensure_input_volume()

    def _ensure_input_volume(self, min_scalar: float = 0.9) -> None:
        """Force the active microphone's Windows input volume up if it's
        below min_scalar - found live: the OS-level input level for the
        configured mic kept silently dropping back down (observed at 36%)
        between sessions, independent of anything in this app's own code,
        making captured audio too quiet for wake-word/STT regardless of
        software gain (AGC only amplifies what's already captured; it can't
        fix a starved OS-level input level). Best-effort: any failure
        (pycaw missing, COM error, no name match) is logged and swallowed -
        this must never block audio startup."""
        try:
            assert self._pa is not None
            index = self._device_index
            if index is None:
                index = self._pa.get_default_input_device_info()["index"]
            device_name = self._pa.get_device_info_by_index(index)["name"]

            import comtypes
            from pycaw.pycaw import IAudioEndpointVolume, AudioUtilities
            from comtypes import CLSCTX_ALL

            comtypes.CoInitialize()
            for d in AudioUtilities.GetAllDevices():
                if str(d.state) != "AudioDeviceState.Active":
                    continue
                if device_name not in (d.FriendlyName or "") and (d.FriendlyName or "") not in device_name:
                    continue
                dev = AudioUtilities.CreateDevice(d._dev)
                interface = dev._dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = interface.QueryInterface(IAudioEndpointVolume)
                current = volume.GetMasterVolumeLevelScalar()
                if current < min_scalar:
                    volume.SetMasterVolumeLevelScalar(1.0, None)
                    log.info(
                        "Mikrofon-Eingangslautstärke war %.0f%%, auf 100%% gesetzt ('%s')",
                        current * 100, d.FriendlyName,
                    )
                break
        except Exception:
            log.warning("Mikrofon-Eingangslautstärke konnte nicht geprüft/gesetzt werden", exc_info=True)

    def _open_stream_locked(self) -> None:
        """Open a new PortAudio stream. Caller must hold self._lock.

        Tries the last-known-good device first (or the PortAudio default on
        first start). If that fails (e.g. the microphone was unplugged or a
        driver rejected the format), falls back to the next available input
        device instead of giving up immediately.
        """
        if self._pa is None:
            raise RuntimeError("PyAudio nicht initialisiert")

        try:
            self._stream = self._open_device_locked(self._device_index)
            return
        except Exception as exc:
            log.warning(
                "Audio-Gerät %s nicht verfügbar (%s), suche Fallback-Gerät",
                self._device_index if self._device_index is not None else "Standard",
                exc,
            )

        for index in self._iter_fallback_devices_locked():
            try:
                self._stream = self._open_device_locked(index)
                self._device_index = index
                log.info("Audio-Stream nutzt Fallback-Gerät Index %d", index)
                return
            except Exception:
                continue

        raise RuntimeError("Kein funktionierendes Audio-Eingabegerät gefunden")

    def _open_device_locked(self, device_index: int | None) -> pyaudio.Stream:
        """Open device_index at the configured rate; on failure, retry the
        SAME device at its native mix rate instead of giving up on it (see
        the resampling comment in __init__). Only if that also fails does
        the caller's fallback-to-a-different-device logic kick in."""
        assert self._pa is not None
        try:
            stream = self._pa.open(
                format=_FORMAT,
                channels=self._channels,
                rate=self._rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self._chunk,
            )
            self._capture_rate = self._rate
            self._resample_state = None
            return stream
        except Exception as exc:
            native_rate = self._native_sample_rate(device_index)
            if native_rate is None or native_rate == self._rate:
                raise
            log.info(
                "Gerät %s unterstützt %d Hz nicht direkt (%s), nutze native Rate %d Hz + Software-Resampling",
                device_index, self._rate, exc, native_rate,
            )
            native_chunk = math.ceil(self._chunk * native_rate / self._rate)
            stream = self._pa.open(
                format=_FORMAT,
                channels=self._channels,
                rate=native_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=native_chunk,
            )
            self._capture_rate = native_rate
            self._resample_state = None
            return stream

    def _native_sample_rate(self, device_index: int | None) -> int | None:
        if device_index is None:
            return None
        assert self._pa is not None
        try:
            info = self._pa.get_device_info_by_index(device_index)
            return int(info["defaultSampleRate"])
        except Exception:
            return None

    def _iter_fallback_devices_locked(self):
        """Yield input-capable device indices other than the one that just failed."""
        assert self._pa is not None
        try:
            count = self._pa.get_device_count()
        except Exception:
            log.exception("Konnte Audio-Geräteliste nicht abfragen")
            return
        for index in range(count):
            if index == self._device_index:
                continue
            try:
                info = self._pa.get_device_info_by_index(index)
            except Exception:
                continue
            if info.get("maxInputChannels", 0) > 0:
                yield index

    def pause(self) -> None:
        """Stop the PortAudio stream but keep PyAudio alive for fast resume."""
        with self._lock:
            if not self._started or self._paused:
                return
            self._paused = True
            stream = self._stream
            self._stream = None
        if stream is not None:
            try:
                if stream.is_active():
                    stream.stop_stream()
                stream.close()
            except Exception:
                log.exception("Fehler beim Pausieren des Audio-Streams")
        log.debug("Audio stream pausiert")

    def resume(self) -> None:
        """Re-open the PortAudio stream on the existing PyAudio instance."""
        with self._lock:
            if not self._started or not self._paused:
                return
            try:
                self._open_stream_locked()
                self._paused = False
            except Exception:
                log.exception("Fehler beim Fortsetzen des Audio-Streams")
                raise
        log.debug("Audio stream fortgesetzt")
        # Deliberately NOT calling _ensure_input_volume() here (found live,
        # serious regression): resume() runs after every single conversation
        # turn (pause/resume around each LLM response), and the volume check
        # does a full COM audio-device enumeration each time - repeated
        # every turn, this measurably bogged down the whole system (user
        # observed the mouse cursor and PC nearly locking up). The device
        # doesn't change between pause/resume within one session, so the
        # check only needs to run once, in start().

    def restart(self) -> bool:
        """Full restart of the audio stream with retry logic. Returns True on success."""
        for attempt in range(1, self._MAX_RESTART_ATTEMPTS + 1):
            log.info("Audio-Stream Neustart (Versuch %d/%d)", attempt, self._MAX_RESTART_ATTEMPTS)
            try:
                self.stop()
                time.sleep(self._RESTART_BACKOFF * attempt)
                self.start()
                log.info("Audio-Stream erfolgreich neu gestartet")
                return True
            except Exception:
                log.exception("Audio-Stream Neustart fehlgeschlagen (Versuch %d)", attempt)
        log.error("Audio-Stream konnte nach %d Versuchen nicht neu gestartet werden", self._MAX_RESTART_ATTEMPTS)
        return False

    def stop(self) -> None:
        with self._lock:
            self._started = False
            self._paused = False
            stream = self._stream
            pa = self._pa
            self._stream = None
            self._pa = None
        if stream is not None:
            try:
                if stream.is_active():
                    stream.stop_stream()
                stream.close()
            except Exception:
                log.exception("Fehler beim Schließen des Audio-Streams")
        if pa is not None:
            try:
                pa.terminate()
            except Exception:
                log.exception("Fehler beim Terminieren von PyAudio")
        log.info("Audio stream gestoppt")

    def read_frames(self, num_frames: int) -> bytes:
        """Read a fixed number of raw int16 frames at self._rate Hz.

        If the device only accepts its native rate (see _open_device_locked),
        reads the proportionally larger number of native-rate frames and
        resamples down via audioop, padding/trimming to exactly
        num_frames * sample_width bytes so callers never see a different
        chunk size than what they configured, resampling active or not.
        """
        with self._lock:
            stream = self._stream
            if stream is None or not self._started:
                raise RuntimeError("AudioStream nicht gestartet")
            capture_rate = self._capture_rate
        target_bytes = num_frames * self._sample_width
        try:
            if capture_rate == self._rate:
                data = stream.read(num_frames, exception_on_overflow=False)
                if len(data) < target_bytes:
                    log.warning(
                        "AudioStream lieferte nur %d/%d Bytes (möglicher Puffer-Unterlauf)",
                        len(data),
                        target_bytes,
                    )
                return data

            native_frames = math.ceil(num_frames * capture_rate / self._rate)
            raw = stream.read(native_frames, exception_on_overflow=False)
            if log.isEnabledFor(logging.DEBUG):
                raw_arr = np.frombuffer(raw, dtype=np.int16)
                raw_rms = float(np.sqrt(np.mean(raw_arr.astype(np.float64) ** 2))) if raw_arr.size else -1.0
                log.debug(
                    "read_frames: requested=%d native_frames=%d len(raw)=%d raw_rms=%.0f",
                    num_frames, native_frames, len(raw), raw_rms,
                )
            with self._lock:
                resampled, self._resample_state = audioop.ratecv(
                    raw, self._sample_width, self._channels,
                    capture_rate, self._rate, self._resample_state,
                )
            if len(resampled) < target_bytes:
                resampled += b"\x00" * (target_bytes - len(resampled))
            elif len(resampled) > target_bytes:
                resampled = resampled[:target_bytes]
            return resampled
        except Exception as exc:
            log.exception("AudioStream Lesefehler")
            raise RuntimeError("AudioStream Lesefehler") from exc

    def read_chunk_bytes(self) -> bytes:
        """Read one configured chunk of raw int16 bytes."""
        return self.read_frames(self._chunk)

    def read_chunk(self) -> np.ndarray:
        """Read one configured chunk as a NumPy int16 array."""
        return np.frombuffer(self.read_chunk_bytes(), dtype=np.int16)

    def flush_input_buffer(self, chunks: int = 3) -> None:
        """Discard a few chunks to re-synchronize after a long STT read."""
        with self._lock:
            if not self._started or self._stream is None:
                return
        log.debug("AudioStream: leere %d Chunks aus dem Eingabepuffer", chunks)
        for _ in range(chunks):
            try:
                self.read_chunk_bytes()
            except Exception:
                log.exception("Fehler beim Flushen des Audio-Streams")
                return

    def __enter__(self) -> AudioStream:
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()


class AudioStreamSource(sr.AudioSource):
    """AudioSource for speech_recognition that reads from a running AudioStream.

    This lets the recognizer consume the same PyAudio stream that is already
    used for wake-word detection, eliminating the delay from re-opening the
    microphone and enabling immediate follow-up speech.
    """

    def __init__(self, audio_stream: AudioStream) -> None:
        # Do not call sr.AudioSource.__init__ because it raises NotImplementedError.
        self._audio_stream = audio_stream
        self.SAMPLE_RATE = audio_stream._rate
        self.SAMPLE_WIDTH = pyaudio.get_sample_size(_FORMAT)
        self.CHUNK = audio_stream._chunk
        self.format = _FORMAT
        self.stream = self

    def read(self, num_frames: int = -1, exception_on_overflow: bool = False) -> bytes:
        """Return one configured chunk of raw int16 bytes.

        speech_recognition always calls read(source.CHUNK), so we serve the
        AudioStream's configured chunk size and ignore num_frames.
        """
        return self._audio_stream.read_frames(self.CHUNK)

    def close(self) -> None:
        """No-op: the underlying AudioStream is managed by its owner."""

    def __enter__(self) -> "AudioStreamSource":
        return self

    def __exit__(self, *args: object) -> None:
        return None


