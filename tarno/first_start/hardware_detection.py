"""Lightweight hardware and audio detection for the first-start wizard."""

from __future__ import annotations

import logging
import platform
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class HardwareProfile:
    os_name: str = ""
    cpu_count: int = 0
    memory_mb: int = 0
    gpu_info: list[str] = field(default_factory=list)
    audio_input_devices: list[dict[str, Any]] = field(default_factory=list)
    audio_output_devices: list[dict[str, Any]] = field(default_factory=list)


def detect_hardware() -> HardwareProfile:
    profile = HardwareProfile(
        os_name=f"{platform.system()} {platform.release()} (Build {platform.version()})",
        cpu_count=getattr(__import__("os"), "cpu_count")() or 0,
    )

    try:
        import psutil

        profile.memory_mb = int(psutil.virtual_memory().total / (1024 * 1024))
    except Exception:
        log.warning("psutil nicht verfügbar; RAM-Erkennung übersprungen")

    try:
        import pyaudio

        pa = pyaudio.PyAudio()
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            device = {"index": i, "name": info.get("name", ""), "channels": info.get("maxInputChannels", 0)}
            if info.get("maxInputChannels", 0) > 0:
                profile.audio_input_devices.append(device)
            if info.get("maxOutputChannels", 0) > 0:
                profile.audio_output_devices.append(device)
        pa.terminate()
    except Exception:
        log.warning("pyaudio nicht verfügbar; Audio-Erkennung übersprungen")

    return profile
