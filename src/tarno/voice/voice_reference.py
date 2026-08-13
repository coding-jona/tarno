"""Default German voice-cloning reference (Thorsten-Voice 2022.10)."""

from __future__ import annotations

from pathlib import Path


def default_reference_path() -> Path:
    """Return the path to the bundled Thorsten reference WAV."""
    # The asset is shipped next to the package root (works for source and
    # PyInstaller one-dir builds).
    root = Path(__file__).resolve().parent.parent
    return root / "assets" / "thorsten_ref.wav"


def default_reference_text() -> str:
    """Return the transcript for the bundled Thorsten reference."""
    root = Path(__file__).resolve().parent.parent
    text_path = root / "assets" / "thorsten_ref.txt"
    if text_path.exists():
        return text_path.read_text(encoding="utf-8").strip()
    return (
        "als hauptlieferant gilt die konventionelle landwirtschaft "
        "mit phosphorhaltigen düngemitteln"
    )
