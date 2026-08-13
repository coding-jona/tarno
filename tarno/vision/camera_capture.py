"""Local webcam capture (Block 7, Phase 61).

Runs entirely locally, matching AudioStream's start()/stop() lifecycle
pattern for the microphone. Frames only ever leave this process if the
VisionObserver's motion gate + Pixtral frame-selection decide a specific
frame is worth analyzing (see vision_provider.py) - no raw video stream is
ever transmitted or persisted to disk.
"""

from __future__ import annotations

import logging
import sys
import threading
import time

import numpy as np

log = logging.getLogger(__name__)

# Windows: volle Fallback-Kette. Manche virtuelle Kameras (z.B. Camo Studio)
# lassen sich mit DirectShow (CAP_DSHOW) auf manchen Windows-10-Systemen nicht
# oder nur mit Schwarzbild öffnen, funktionieren aber über Media Foundation
# (CAP_MSMF) - ein bekanntes, dokumentiertes OpenCV/DirectShow-Problem bei
# virtuellen Kameras (github.com/opencv/opencv#19746, #23373).
_WINDOWS_BACKEND_FALLBACK_ORDER = ("CAP_DSHOW", "CAP_MSMF", "CAP_ANY")

# Heuristische Bezeichner fuer virtuelle/Screen-Capture-Quellen, die in
# OpenCV leider nicht zuverlaessig als solche gekennzeichnet sind. Wir
# nutzen sie nur als Log-/Warn-Hinweis, nicht als harte Ausgrenzung.
_VIRTUAL_SOURCE_HINTS = ("obs", "virtual", "camo", "manycam", "droidcam",
                         "xsplit", "streamlabs", "screen", "desktop", "snap")


class CameraCapture:
    """Thin wrapper around cv2.VideoCapture with an explicit start/stop
    lifecycle. Fails soft: start() returns False (not an exception) if no
    camera is available, so the caller (VisionObserver) can disable itself
    gracefully instead of crashing the whole ProactiveEngine."""

    _DEGENERATE_MEAN_THRESHOLD = 2.0
    _DEGENERATE_STD_THRESHOLD = 2.0
    # Live am Backend-Log bestaetigt (2026-07-31): mit 15 Frames/30ms wurde
    # CAP_MSMF/CAP_ANY faelschlich als "eingefroren" verworfen, obwohl die
    # Kamera frei und funktionsfaehig war. Ursache: ein bekanntes OpenCV-
    # Windows-Verhalten, bei dem cap.read() kurz nach dem Oeffnen denselben,
    # noch nicht aktualisierten Puffer-Frame zurueckgibt, wenn der Abstand
    # zwischen den Reads kuerzer ist als die tatsaechliche Frame-Periode der
    # Kamera (bei ueblichen 15-30fps sind das schon 33-66ms pro Frame, plus
    # Zeit fuer Autobelichtung/-fokus-Verhandlung direkt nach dem Oeffnen,
    # die oft nochmal deutlich laenger dauert). 30ms Abstand war also kuerzer
    # als ein einzelner Frame - fast jeder Vergleich traf zwangslaeufig auf
    # zwei Reads desselben gepufferten Bildes. Jetzt 100ms Abstand (klar
    # ueber jeder ueblichen Frame-Periode) bei weniger Frames, damit die
    # Gesamt-Wartezeit beim Oeffnen (~1s) nicht unangenehm lang wird.
    _WARMUP_FRAMES_FOR_VALIDATION = 10
    _WARMUP_DELAY_FOR_VALIDATION = 0.1
    _FROZEN_FRAMES_TOLERANCE = 0.95  # Anteil identischer Pixel, ab der wir "eingefroren" sagen

    def __init__(self, device_index: int = 0, device_name: str = "") -> None:
        self._device_index = device_index
        self._device_name = device_name
        self._cap = None
        self._lock = threading.Lock()
        self._opened_index: int | None = None
        self._opened_backend: str = ""

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._cap is not None and self._cap.isOpened()

    @property
    def device_label(self) -> str:
        if self._opened_index is None:
            return "nicht geoeffnet"
        return f"index {self._opened_index} ({self._opened_backend})"

    def start(self) -> bool:
        try:
            import cv2
        except ImportError:
            log.warning("opencv-python nicht installiert - Vision-Layer deaktiviert")
            return False

        with self._lock:
            if self._cap is not None:
                return True

            target_index = self._resolve_device_index()
            if target_index is None:
                log.warning("Keine passende Kamera anhand von device_name='%s' gefunden", self._device_name)
                return False

            tried = []
            for backend_name in self._candidate_backends():
                backend = getattr(cv2, backend_name, None)
                if backend is None:
                    continue  # dieser cv2-Build kennt dieses Backend nicht
                tried.append(backend_name)
                cap = cv2.VideoCapture(target_index, backend)
                if not cap.isOpened():
                    cap.release()
                    log.debug(
                        "Kamera (Index %d, Backend %s) konnte nicht geöffnet werden",
                        target_index, backend_name,
                    )
                    continue
                if not self._validate_frames_locked(cap, index=target_index, backend=backend_name):
                    cap.release()
                    continue
                self._cap = cap
                self._opened_index = target_index
                self._opened_backend = backend_name
                log.info(
                    "Kamera gestartet (Index %d, Backend %s, device_name='%s')",
                    target_index, backend_name, self._device_name or "-",
                )
                return True

            log.warning(
                "Kamera (Index %d) konnte mit keinem Backend (%s) geöffnet werden",
                target_index, ", ".join(tried) or "keines verfügbar",
            )
            return False

    def _resolve_device_index(self) -> int | None:
        """Determine the camera index to open. device_name takes precedence:
        a numeric string is interpreted as an index; otherwise we enumerate
        and pick the first device whose generated name contains the string."""
        name = (self._device_name or "").strip()
        if not name:
            return self._device_index
        if name.isdigit():
            return int(name)

        for device in self.enumerate_devices():
            if name.lower() in device["label"].lower():
                return int(device["index"])
        log.warning(
            "device_name='%s' passt auf keine gefundene Kamera (%s) - verwende device_index=%d",
            name,
            ", ".join(d["label"] for d in self.enumerate_devices()),
            self._device_index,
        )
        return self._device_index

    @classmethod
    def enumerate_devices(cls, max_index: int = 10) -> list[dict[str, object]]:
        """Enumerate usable local camera devices up to max_index. Each entry
        contains index, backend and a generated label. Devices that only
        deliver black or frozen frames are skipped."""
        try:
            import cv2
        except ImportError:
            return []

        found: list[dict[str, object]] = []
        for index in range(max_index):
            for backend_name in cls._candidate_backends_win32():
                backend = getattr(cv2, backend_name, None)
                if backend is None:
                    continue
                cap = cv2.VideoCapture(index, backend)
                if not cap.isOpened():
                    cap.release()
                    continue
                if not cls._validate_candidate(cap, index=index, backend=backend_name):
                    cap.release()
                    continue
                backend_short = backend_name.replace("CAP_", "")
                label = f"Kamera {index} ({backend_short})"
                found.append({"index": index, "backend": backend_name, "label": label})
                cap.release()
                break  # one backend per index is enough
        return found

    @classmethod
    def _candidate_backends_win32(cls) -> list[str]:
        """Backend names used for device enumeration and start fallback."""
        if sys.platform == "win32":
            return list(_WINDOWS_BACKEND_FALLBACK_ORDER)
        return ["CAP_ANY"]

    def _candidate_backends(self) -> list[str]:
        """Backward-compatible instance accessor."""
        return self._candidate_backends_win32()

    @classmethod
    def _validate_candidate(cls, cap, index: int, backend: str) -> bool:
        """OpenCV-only validation: readable, non-black and not frozen."""
        first_valid = None
        last_valid = None
        for _ in range(cls._WARMUP_FRAMES_FOR_VALIDATION):
            ok, frame = cap.read()
            if cls._WARMUP_DELAY_FOR_VALIDATION:
                time.sleep(cls._WARMUP_DELAY_FOR_VALIDATION)
            if not ok or frame is None:
                continue
            mean = float(frame.mean())
            std = float(frame.std())
            if mean > cls._DEGENERATE_MEAN_THRESHOLD or std > cls._DEGENERATE_STD_THRESHOLD:
                if first_valid is None:
                    first_valid = frame
                last_valid = frame
        if first_valid is None:
            log.warning("Kamera (Index %d, Backend %s) liefert nur schwarze/degenerierte Frames", index, backend)
            return False
        if last_valid is not None and last_valid is not first_valid and cls._is_frozen(first_valid, last_valid):
            log.warning("Kamera (Index %d, Backend %s) liefert eingefrorene Frames (Screen-Capture?)", index, backend)
            return False
        return True

    @classmethod
    def _is_frozen(cls, a: np.ndarray, b: np.ndarray) -> bool:
        """Return True if two frames are almost pixel-identical, indicating
        a static/screen-capture source rather than a live camera."""
        if a.shape != b.shape:
            return False
        diff = np.abs(a.astype(np.float32) - b.astype(np.float32)).mean()
        # 255 * (1 - tolerance) is the diff threshold for "effectively identical"
        return diff < 255 * (1 - cls._FROZEN_FRAMES_TOLERANCE)

    def _validate_frames_locked(self, cap, index: int, backend: str) -> bool:
        """Instance validation wrapper around the class method."""
        return self._validate_candidate(cap, index=index, backend=backend)

    @classmethod
    def _has_virtual_source_hint(cls, label: str) -> bool:
        return any(hint in label.lower() for hint in _VIRTUAL_SOURCE_HINTS)

    def stop(self) -> None:
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
        log.info("Kamera gestoppt")

    def read_frame(self) -> np.ndarray | None:
        """Read one frame (BGR, as OpenCV provides it). Returns None if the
        camera isn't started or the read failed."""
        with self._lock:
            if self._cap is None:
                return None
            ok, frame = self._cap.read()
        if not ok:
            return None
        return frame

    def __enter__(self) -> "CameraCapture":
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()
