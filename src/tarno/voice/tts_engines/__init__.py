"""Local TTS engine adapters for TARNO.

Engines:
- PiperEngine: fast, local, ONNX-based, no voice cloning.
- NeuTTSEngine: local voice cloning (planned; requires neutts package).
- EdgeTTSEngine: cloud/network fallback using edge-tts (no API key).
"""

from __future__ import annotations

from tarno.voice.tts_engines.base import BaseTTSEngine, TTSAudioChunk
from tarno.voice.tts_engines.edge import EdgeTTSEngine
from tarno.voice.tts_engines.piper import PiperEngine

try:
    from tarno.voice.tts_engines.neutts import NeuTTSEngine
except ImportError:
    NeuTTSEngine = None  # type: ignore[assignment, misc]


def get_tts_engine(engine_name: str, config: dict[str, object]) -> BaseTTSEngine:
    """Factory for a TTS engine by name.

    Args:
        engine_name: one of the supported engine identifiers.
        config: engine-specific settings from the audio/tts config block.

    Returns:
        An initialised TTSEngine instance.

    Raises:
        ValueError: if the engine is not known.
        ImportError: if the engine is requested but its package is not installed.
    """
    name = (engine_name or "piper").lower()
    if name == "neutts":
        if NeuTTSEngine is None:
            raise ImportError("neutts package is not installed")
        return NeuTTSEngine(config)
    if name == "piper":
        return PiperEngine(config)
    if name in ("edge", "edge-tts"):
        return EdgeTTSEngine(config)
    raise ValueError(f"Unknown TTS engine: {engine_name}")


__all__ = [
    "BaseTTSEngine",
    "TTSAudioChunk",
    "EdgeTTSEngine",
    "PiperEngine",
    "NeuTTSEngine",
    "get_tts_engine",
]
