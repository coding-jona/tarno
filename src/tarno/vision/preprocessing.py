"""Frame preprocessing before any vision-model API call (Block 7, Phase 64).

Downscales to ~512-720px longest edge and JPEG-encodes before a frame ever
leaves the process - directly reduces API payload size/cost/latency,
matching the pattern OpenAI's GPT-4o Vision uses (per the research note in
Tarno Plans/tarno-70-phase-masterplan.md's Block 7 section).
"""

from __future__ import annotations

import base64
import logging

import numpy as np

log = logging.getLogger(__name__)


def downscale_and_encode_jpeg(frame: np.ndarray, max_edge: int = 640, quality: int = 80) -> bytes:
    """Resize *frame* (BGR numpy array) so its longest edge is at most
    *max_edge*, then JPEG-encode. Returns raw JPEG bytes."""
    import cv2

    height, width = frame.shape[:2]
    longest_edge = max(height, width)
    if longest_edge > max_edge:
        scale = max_edge / longest_edge
        new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
        frame = cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)

    ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("JPEG-Encoding fehlgeschlagen")
    jpeg_bytes = encoded.tobytes()
    log.info(
        "Vision-Frame vorbereitet: %dx%d -> %dx%d, %d Bytes (quality=%d)",
        width, height, frame.shape[1], frame.shape[0], len(jpeg_bytes), quality,
    )
    return jpeg_bytes


def frame_to_data_url(frame: np.ndarray, max_edge: int = 640, quality: int = 80) -> str:
    """Convenience: downscale + JPEG-encode + base64, ready for an
    OpenAI-style image_url content block."""
    jpeg_bytes = downscale_and_encode_jpeg(frame, max_edge, quality)
    b64 = base64.b64encode(jpeg_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def uploaded_bytes_to_data_url(data: bytes, max_edge: int = 640, quality: int = 80) -> str:
    """Same pipeline as frame_to_data_url, but for arbitrary encoded image
    bytes (e.g. a user-picked JPEG/PNG/WebP file from the WinUI chat upload)
    instead of a raw camera frame - decodes via cv2.imdecode first so both
    image sources share one downscale/encode codepath."""
    import cv2

    array = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Bilddaten konnten nicht dekodiert werden")
    return frame_to_data_url(frame, max_edge, quality)
