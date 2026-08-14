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
