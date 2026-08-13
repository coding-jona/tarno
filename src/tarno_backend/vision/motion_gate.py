"""Local motion detection (Block 7, Phase 62).

A pure cost brake, not a relevance judgment - it only answers "did anything
move between frames", never "is this important". The actual "what matters"
decision belongs to Pixtral's frame-selection prompt (see vision_provider.py),
matching the design principle established for this block: code does cheap
mechanical filtering, the model does the judgment call.
"""

from __future__ import annotations

import numpy as np


class MotionGate:
    """Frame-diff-based motion detector (grayscale mean absolute difference)."""

    def __init__(self, threshold: float = 25.0) -> None:
        self._threshold = threshold
        self._previous_gray: np.ndarray | None = None

    def detect(self, frame: np.ndarray) -> bool:
        """Returns True if *frame* differs enough from the previously seen
        frame to count as motion. Always False on the first call (nothing to
        compare against yet) - that frame just seeds the baseline."""
        import cv2

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if self._previous_gray is None:
            self._previous_gray = gray
            return False

        diff = cv2.absdiff(self._previous_gray, gray)
        self._previous_gray = gray
        mean_diff = float(np.mean(diff))
        return mean_diff >= self._threshold

    def reset(self) -> None:
        self._previous_gray = None
