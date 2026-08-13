"""Vision-Layer Kalibrierung/Latenzmessung (Block 7, Phase 70).

Misst die echte End-to-End-Latenz zwischen einem erkannten Bewegungs-
Trigger und der geparsten Modell-Antwort - einmalig gegen die echte Kamera
und die echte Mistral-Vision-API (kein Mock), um die in VisionConfig
konfigurierten Werte (motion_threshold, candidate_frames, downscale_max_edge)
gegen reale Bedingungen zu prüfen und bei Bedarf feinzujustieren.

Nutzt echte API-Aufrufe - nicht Teil der pytest-Suite (siehe
tests/test_vision_block7.py für die kostenlose, netzwerkfreie Testabdeckung).

Usage:
    py -3.12 workspace/debug/tools/vision_calibration.py
    py -3.12 workspace/debug/tools/vision_calibration.py --device-index 1 --motion-threshold 15
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "src"))

from tarno_backend.security.secrets import SecretsVault  # noqa: E402
from tarno_backend.vision.camera_capture import CameraCapture  # noqa: E402
from tarno_backend.vision.motion_gate import MotionGate  # noqa: E402
from tarno_backend.vision.vision_provider import MistralVisionProvider  # noqa: E402


def run_calibration(
    device_index: int,
    motion_threshold: float,
    candidate_frames: int,
    downscale_max_edge: int,
    jpeg_quality: int,
    model: str,
    max_wait_seconds: float,
) -> int:
    vault = SecretsVault(backend="keyring")
    api_key = vault.get("MISTRAL_API_KEY") or ""
    if not api_key:
        print("[FEHLER] Kein MISTRAL_API_KEY konfiguriert - Kalibrierung nicht möglich.")
        return 1

    camera = CameraCapture(device_index=device_index)
    if not camera.start():
        print(f"[FEHLER] Kamera (Index {device_index}) konnte nicht geöffnet werden.")
        return 1

    provider = MistralVisionProvider(api_key=api_key, model=model)
    gate = MotionGate(threshold=motion_threshold)

    print(f"Kalibrierung gestartet (Kamera {device_index}, Schwellenwert {motion_threshold}).")
    print("Bewege dich vor der Kamera, um einen Trigger auszulösen...")

    try:
        start = time.monotonic()
        motion_detected_at = None

        while time.monotonic() - start < max_wait_seconds:
            frame = camera.read_frame()
            if frame is None:
                continue
            if gate.detect(frame):
                motion_detected_at = time.monotonic()
                trigger_frame = frame
                break
        else:
            print(f"[TIMEOUT] Keine Bewegung innerhalb von {max_wait_seconds:.0f}s erkannt.")
            return 1

        print(f"Bewegung erkannt nach {motion_detected_at - start:.2f}s. Sammle Kandidaten-Frames...")

        candidates = [trigger_frame]
        for _ in range(candidate_frames - 1):
            f = camera.read_frame()
            if f is not None:
                candidates.append(f)
        collection_done_at = time.monotonic()

        print(f"{len(candidates)} Kandidaten-Frames gesammelt in {collection_done_at - motion_detected_at:.2f}s. Frage Modell an...")

        assessment = provider.assess_frames(
            candidates, max_edge=downscale_max_edge, jpeg_quality=jpeg_quality,
        )
        assessed_at = time.monotonic()

        if assessment is None:
            print("[FEHLER] Modell-Anfrage fehlgeschlagen oder nicht geparst.")
            return 1

        print("\n--- Ergebnis ---")
        print(f"Relevant:        {assessment.relevant}")
        print(f"Score:           {assessment.score}")
        print(f"Begründung:      {assessment.reason}")
        print(f"Gewähltes Frame: {assessment.frame_index}")
        print("\n--- Latenz-Aufschlüsselung ---")
        print(f"Bewegung -> Frame-Sammlung abgeschlossen: {collection_done_at - motion_detected_at:.2f}s")
        print(f"Frame-Sammlung -> Modell-Antwort:          {assessed_at - collection_done_at:.2f}s")
        print(f"GESAMT (Bewegung -> Modell-Antwort):       {assessed_at - motion_detected_at:.2f}s")

        return 0
    finally:
        camera.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--device-index", type=int, default=0)
    parser.add_argument("--motion-threshold", type=float, default=25.0)
    parser.add_argument("--candidate-frames", type=int, default=5)
    parser.add_argument("--downscale-max-edge", type=int, default=640)
    parser.add_argument("--jpeg-quality", type=int, default=80)
    parser.add_argument("--model", default="mistral-large-latest")
    parser.add_argument("--max-wait-seconds", type=float, default=30.0)
    args = parser.parse_args()

    return run_calibration(
        args.device_index, args.motion_threshold, args.candidate_frames,
        args.downscale_max_edge, args.jpeg_quality, args.model, args.max_wait_seconds,
    )


if __name__ == "__main__":
    sys.exit(main())
