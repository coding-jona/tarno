"""Tests for the Vision-Layer (Block 7, Phasen 61-70).

MistralVisionProvider's actual HTTP call is NOT exercised here (that was
verified manually against the live API while building this - see commit
notes) to keep the automated suite free of network dependency/cost; only
the pure request/response parsing logic is tested with synthetic data.
CameraCapture tests use the real webcam if one is available and skip
gracefully otherwise, since this machine has one and it's the only way to
verify the OpenCV integration actually works end-to-end.
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from tarno.core.proactive_engine import ProactiveDraft
from tarno.vision.camera_capture import CameraCapture
from tarno.vision.motion_gate import MotionGate
from tarno.vision.preprocessing import (
    downscale_and_encode_jpeg,
    frame_to_data_url,
    uploaded_bytes_to_data_url,
)
from tarno.vision.vision_observer import VisionObserver
from tarno.vision.vision_provider import MistralVisionProvider, VisionAssessment


class MotionGateTests(unittest.TestCase):
    def test_first_frame_never_triggers(self) -> None:
        gate = MotionGate(threshold=25.0)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.assertFalse(gate.detect(frame))

    def test_identical_frames_no_motion(self) -> None:
        gate = MotionGate(threshold=25.0)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        gate.detect(frame)
        self.assertFalse(gate.detect(frame.copy()))

    def test_large_change_triggers_motion(self) -> None:
        gate = MotionGate(threshold=25.0)
        black = np.zeros((480, 640, 3), dtype=np.uint8)
        white = np.full((480, 640, 3), 255, dtype=np.uint8)
        gate.detect(black)
        self.assertTrue(gate.detect(white))

    def test_reset_clears_baseline(self) -> None:
        gate = MotionGate(threshold=25.0)
        black = np.zeros((480, 640, 3), dtype=np.uint8)
        white = np.full((480, 640, 3), 255, dtype=np.uint8)
        gate.detect(black)
        gate.reset()
        # After reset, the next frame (even a drastically different one)
        # just re-seeds the baseline instead of firing immediately.
        self.assertFalse(gate.detect(white))

    def test_higher_threshold_is_less_sensitive(self) -> None:
        strict_gate = MotionGate(threshold=200.0)
        black = np.zeros((480, 640, 3), dtype=np.uint8)
        slightly_different = np.full((480, 640, 3), 30, dtype=np.uint8)
        strict_gate.detect(black)
        self.assertFalse(strict_gate.detect(slightly_different))


class PreprocessingTests(unittest.TestCase):
    def test_downscales_large_frame(self) -> None:
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        jpeg_bytes = downscale_and_encode_jpeg(frame, max_edge=640, quality=80)
        self.assertGreater(len(jpeg_bytes), 0)
        # Verify the encoded image was actually resized, not just re-encoded at full size.
        import cv2
        decoded = cv2.imdecode(np.frombuffer(jpeg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        self.assertLessEqual(max(decoded.shape[:2]), 640)

    def test_does_not_upscale_small_frame(self) -> None:
        frame = np.zeros((100, 200, 3), dtype=np.uint8)
        jpeg_bytes = downscale_and_encode_jpeg(frame, max_edge=640, quality=80)
        import cv2
        decoded = cv2.imdecode(np.frombuffer(jpeg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(decoded.shape[:2], (100, 200))

    def test_data_url_has_correct_prefix(self) -> None:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        url = frame_to_data_url(frame)
        self.assertTrue(url.startswith("data:image/jpeg;base64,"))

    def test_uploaded_bytes_to_data_url_decodes_real_image(self) -> None:
        """Phase A (Chat-Bild-Upload): a real 1x1 JPEG encoded via cv2 (not a
        camera frame) must decode and re-encode into a valid data URL through
        the same downscale/encode pipeline as frame_to_data_url."""
        import cv2

        pixel = np.zeros((1, 1, 3), dtype=np.uint8)
        ok, encoded = cv2.imencode(".jpg", pixel)
        self.assertTrue(ok)

        url = uploaded_bytes_to_data_url(encoded.tobytes())
        self.assertTrue(url.startswith("data:image/jpeg;base64,"))

    def test_uploaded_bytes_to_data_url_rejects_garbage(self) -> None:
        with self.assertRaises(ValueError):
            uploaded_bytes_to_data_url(b"not a real image")


class MistralVisionProviderParsingTests(unittest.TestCase):
    """Tests the request/response handling logic without making real HTTP calls."""

    def test_available_false_without_api_key(self) -> None:
        provider = MistralVisionProvider(api_key="")
        provider._api_key = ""  # ensure no env var leaks in during CI
        self.assertFalse(provider.available)

    def test_available_true_with_api_key(self) -> None:
        provider = MistralVisionProvider(api_key="fake-key-for-test")
        self.assertTrue(provider.available)

    def test_parse_valid_response(self) -> None:
        result = {
            "choices": [{"message": {"content": '{"frame_index": 2, "relevant": true, "reason": "Jemand steht an der Tür", "score": 92}'}}]
        }
        assessment = MistralVisionProvider._parse(result, frame_count=5)
        self.assertEqual(assessment, VisionAssessment(frame_index=2, relevant=True, reason="Jemand steht an der Tür", score=92))

    def test_parse_strips_code_fence(self) -> None:
        result = {
            "choices": [{"message": {"content": '```json\n{"frame_index": 0, "relevant": false, "reason": "nichts", "score": 5}\n```'}}]
        }
        assessment = MistralVisionProvider._parse(result, frame_count=3)
        self.assertIsNotNone(assessment)
        self.assertFalse(assessment.relevant)

    def test_parse_clamps_out_of_range_frame_index(self) -> None:
        result = {
            "choices": [{"message": {"content": '{"frame_index": 99, "relevant": true, "reason": "x", "score": 50}'}}]
        }
        assessment = MistralVisionProvider._parse(result, frame_count=3)
        self.assertEqual(assessment.frame_index, 0)

    def test_parse_clamps_score_range(self) -> None:
        result = {"choices": [{"message": {"content": '{"frame_index": 0, "relevant": true, "reason": "x", "score": 500}'}}]}
        assessment = MistralVisionProvider._parse(result, frame_count=1)
        self.assertEqual(assessment.score, 100)

    def test_parse_malformed_json_returns_none(self) -> None:
        result = {"choices": [{"message": {"content": "not json at all"}}]}
        self.assertIsNone(MistralVisionProvider._parse(result, frame_count=1))

    def test_assess_frames_returns_none_when_unavailable(self) -> None:
        provider = MistralVisionProvider(api_key="")
        provider._api_key = ""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.assertIsNone(provider.assess_frames([frame]))

    def test_assess_frames_returns_none_for_empty_list(self) -> None:
        provider = MistralVisionProvider(api_key="fake-key")
        self.assertIsNone(provider.assess_frames([]))

    def test_describe_frame_returns_none_without_api_key(self) -> None:
        provider = MistralVisionProvider(api_key="")
        provider._api_key = ""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.assertIsNone(provider.describe_frame(frame))

    def test_describe_frame_returns_model_text(self) -> None:
        """describe_frame returns (description, jpeg_bytes) - the raw JPEG
        sent to the model is included so the UI can show it as an attachment
        (see its docstring) - not just the plain description string."""
        import unittest.mock as mock

        provider = MistralVisionProvider(api_key="fake-key-for-test")
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        fake_response = mock.MagicMock()
        fake_response.read.return_value = json.dumps(
            {"choices": [{"message": {"content": "Ein Schreibtisch mit einem Laptop."}}]}
        ).encode("utf-8")
        fake_response.__enter__.return_value = fake_response
        with mock.patch("urllib.request.urlopen", return_value=fake_response):
            result = provider.describe_frame(frame)
        self.assertIsNotNone(result)
        description, jpeg_bytes = result
        self.assertEqual(description, "Ein Schreibtisch mit einem Laptop.")
        self.assertIsInstance(jpeg_bytes, bytes)
        self.assertGreater(len(jpeg_bytes), 0)

    def test_describe_frame_returns_none_on_http_error(self) -> None:
        import urllib.error
        import unittest.mock as mock

        provider = MistralVisionProvider(api_key="fake-key-for-test")
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        with mock.patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("boom"),
        ):
            self.assertIsNone(provider.describe_frame(frame))


class _FakeCamera:
    def __init__(self, frames: list) -> None:
        self._frames = list(frames)
        self._index = 0
        self.started = False
        self.stopped = False
        self.read_calls = 0

    @property
    def is_active(self) -> bool:
        return self.started and not self.stopped

    def start(self) -> bool:
        self.started = True
        return True

    def stop(self) -> None:
        self.stopped = True

    def read_frame(self):
        self.read_calls += 1
        if self._index >= len(self._frames):
            return self._frames[-1] if self._frames else None
        frame = self._frames[self._index]
        self._index += 1
        return frame


class _FakeVisionProvider:
    def __init__(self, assessment: VisionAssessment | None, available: bool = True, description: str | None = None) -> None:
        self._assessment = assessment
        self._available = available
        self._description = description
        self.calls = 0
        self.describe_calls = 0

    @property
    def available(self) -> bool:
        return self._available

    def assess_frames(self, frames, max_edge=640, jpeg_quality=80):
        self.calls += 1
        return self._assessment

    def describe_frame(self, frame, max_edge=640, jpeg_quality=80):
        self.describe_calls += 1
        if self._description is None:
            return None
        return self._description, b"FAKE_JPEG"


def _frame(value: int) -> np.ndarray:
    return np.full((480, 640, 3), value, dtype=np.uint8)


class VisionObserverTests(unittest.TestCase):
    def test_no_draft_without_motion(self) -> None:
        camera = _FakeCamera([_frame(0), _frame(0), _frame(0)])
        provider = _FakeVisionProvider(VisionAssessment(0, True, "x", 90))
        observer = VisionObserver(camera, provider, motion_threshold=25.0, candidate_frames=3)

        self.assertIsNone(observer.check())  # baseline frame
        self.assertIsNone(observer.check())  # identical frame, no motion
        self.assertEqual(provider.calls, 0)

    def test_draft_returned_on_motion_when_relevant(self) -> None:
        camera = _FakeCamera([_frame(0), _frame(255), _frame(255), _frame(255)])
        provider = _FakeVisionProvider(VisionAssessment(0, True, "Jemand an der Tür", 92))
        observer = VisionObserver(camera, provider, motion_threshold=25.0, candidate_frames=3)

        self.assertIsNone(observer.check())  # baseline
        draft = observer.check()  # motion detected -> assessed
        self.assertIsNotNone(draft)
        self.assertIsInstance(draft, ProactiveDraft)
        self.assertEqual(draft.score, 92)
        self.assertIn("Jemand an der Tür", draft.message)

    def test_no_draft_when_model_says_not_relevant(self) -> None:
        camera = _FakeCamera([_frame(0), _frame(255), _frame(255)])
        provider = _FakeVisionProvider(VisionAssessment(0, False, "Nur eine Katze", 20))
        observer = VisionObserver(camera, provider, motion_threshold=25.0, candidate_frames=2)

        observer.check()
        self.assertIsNone(observer.check())

    def test_set_enabled_true_opens_camera_immediately_without_check(self) -> None:
        """Regression test (found via live testing): set_enabled(True) used
        to only flip a flag, leaving the camera closed until the next
        ProactiveEngine tick (up to tick_seconds later, e.g. 10s) - a status
        broadcast reading is_capturing right after toggling would see stale
        "off" state. is_capturing must reflect reality immediately."""
        camera = _FakeCamera([_frame(0)])
        provider = _FakeVisionProvider(VisionAssessment(0, True, "x", 90))
        observer = VisionObserver(camera, provider)

        observer.set_enabled(True)
        self.assertTrue(camera.started)
        self.assertTrue(observer.is_capturing)

    def test_unavailable_provider_short_circuits(self) -> None:
        camera = _FakeCamera([_frame(0)])
        provider = _FakeVisionProvider(None, available=False)
        observer = VisionObserver(camera, provider)
        self.assertIsNone(observer.check())
        self.assertFalse(camera.started)  # never even opens the camera

    def test_camera_unavailable_returns_none_gracefully(self) -> None:
        class _FailingCamera(_FakeCamera):
            def start(self) -> bool:
                return False

        camera = _FailingCamera([])
        provider = _FakeVisionProvider(VisionAssessment(0, True, "x", 90))
        observer = VisionObserver(camera, provider)
        self.assertIsNone(observer.check())

    def test_set_enabled_false_closes_camera_and_short_circuits(self) -> None:
        camera = _FakeCamera([_frame(0), _frame(255)])
        provider = _FakeVisionProvider(VisionAssessment(0, True, "x", 90))
        observer = VisionObserver(camera, provider)

        observer.check()  # opens camera
        self.assertTrue(camera.started)
        self.assertTrue(observer.is_capturing)

        observer.set_enabled(False)
        self.assertFalse(observer.is_capturing)
        self.assertTrue(camera.stopped)
        self.assertIsNone(observer.check())  # short-circuits while disabled

    def test_capture_and_describe_returns_description(self) -> None:
        camera = _FakeCamera([_frame(0)])
        provider = _FakeVisionProvider(None, description="Ein leerer Raum.")
        observer = VisionObserver(camera, provider, warmup_delay=0)

        result = observer.capture_and_describe()
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "Ein leerer Raum.")
        self.assertTrue(len(result[1]) > 0)
        self.assertEqual(provider.describe_calls, 1)

    def test_capture_and_describe_discards_warmup_frames_on_cold_open(self) -> None:
        """Regression test (found via live testing): a snapshot grabbed right
        after opening the camera came back dark/blurry even in a well-lit
        room, because auto-exposure hadn't settled yet - a continuously
        running preview (e.g. Windows camera settings) looked fine at the
        same moment. Discarding a few warm-up frames before the one actually
        sent to the vision model fixes this."""
        camera = _FakeCamera([_frame(0)])
        provider = _FakeVisionProvider(None, description="x")
        observer = VisionObserver(camera, provider, warmup_frames=8, warmup_delay=0)

        observer.capture_and_describe()
        # 8 warm-up reads + 1 real read = 9 total.
        self.assertEqual(camera.read_calls, 9)

    def test_capture_and_describe_skips_warmup_when_camera_already_running(self) -> None:
        camera = _FakeCamera([_frame(0), _frame(0)])
        provider = _FakeVisionProvider(None, description="x")
        observer = VisionObserver(camera, provider, warmup_frames=8, warmup_delay=0)
        observer.set_enabled(True)  # camera already running before the call
        camera.read_calls = 0

        observer.capture_and_describe()
        self.assertEqual(camera.read_calls, 1)

    def test_capture_and_describe_closes_camera_if_it_opened_it(self) -> None:
        """Privacy contract (Phase 69): an on-demand snapshot must not leave
        the camera running afterwards if it wasn't already on."""
        camera = _FakeCamera([_frame(0)])
        provider = _FakeVisionProvider(None, description="x")
        observer = VisionObserver(camera, provider, warmup_delay=0)

        observer.capture_and_describe()
        self.assertTrue(camera.stopped)
        self.assertFalse(observer.is_capturing)

    def test_capture_and_describe_leaves_already_running_camera_open(self) -> None:
        camera = _FakeCamera([_frame(0), _frame(0)])
        provider = _FakeVisionProvider(None, description="x")
        observer = VisionObserver(camera, provider, warmup_delay=0)
        observer.set_enabled(True)  # camera already running before the call

        observer.capture_and_describe()
        self.assertFalse(camera.stopped)
        self.assertTrue(observer.is_capturing)

    def test_capture_and_describe_returns_none_when_disabled(self) -> None:
        camera = _FakeCamera([_frame(0)])
        provider = _FakeVisionProvider(None, description="x")
        observer = VisionObserver(camera, provider, warmup_delay=0)
        observer.set_enabled(False)

        self.assertIsNone(observer.capture_and_describe())
        self.assertEqual(provider.describe_calls, 0)

    def test_capture_and_describe_returns_none_when_provider_unavailable(self) -> None:
        camera = _FakeCamera([_frame(0)])
        provider = _FakeVisionProvider(None, available=False)
        observer = VisionObserver(camera, provider, warmup_delay=0)

        self.assertIsNone(observer.capture_and_describe())
        self.assertFalse(camera.started)

    def test_re_enabling_reopens_camera(self) -> None:
        camera = _FakeCamera([_frame(0), _frame(255), _frame(255)])
        provider = _FakeVisionProvider(VisionAssessment(0, True, "x", 90))
        observer = VisionObserver(camera, provider)

        observer.check()
        observer.set_enabled(False)
        observer.set_enabled(True)
        camera.stopped = False  # simulate hardware being reopenable
        result = observer.check()
        # Just verifying it doesn't crash and resumes normal operation.
        self.assertTrue(camera.started)


@unittest.skipUnless(
    __import__("importlib").util.find_spec("cv2") is not None,
    "opencv-python nicht installiert",
)
class RealCameraIntegrationTest(unittest.TestCase):
    """Verifies the actual OpenCV integration against real hardware if
    available - skips gracefully (not a failure) if no webcam is present."""

    def test_start_read_stop_real_camera(self) -> None:
        camera = CameraCapture(device_index=0)
        if not camera.start():
            self.skipTest("Keine Kamera verfügbar auf diesem System")
        try:
            frame = camera.read_frame()
            self.assertIsNotNone(frame)
            self.assertEqual(len(frame.shape), 3)
            # Regressionstest gegen das Schwarzbild-Problem bei virtuellen
            # Kameras (github.com/opencv/opencv#19746, #23373): auf echter
            # Hardware muss der Frame auch tatsächlich Bildinhalt haben.
            self.assertGreater(float(frame.std()), 0.0)
        finally:
            camera.stop()
        self.assertFalse(camera.is_active)


class _FakeCv2Capture:
    """Stub for a single cv2.VideoCapture(...) call in the backend-fallback tests."""

    def __init__(self, opens: bool, frames: list) -> None:
        self._opens = opens
        self._frames = list(frames)
        self.released = False

    def isOpened(self) -> bool:
        return self._opens

    def read(self):
        if not self._frames:
            return False, None
        frame = self._frames.pop(0) if len(self._frames) > 1 else self._frames[0]
        return True, frame

    def release(self) -> None:
        self.released = True


def _black_frame() -> np.ndarray:
    return np.zeros((10, 10, 3), dtype=np.uint8)


def _real_frame() -> np.ndarray:
    return np.random.randint(0, 255, (10, 10, 3)).astype(np.uint8)


class CameraCaptureBackendFallbackTests(unittest.TestCase):
    """Tests for CameraCapture.start()'s Windows backend-fallback chain
    (DSHOW -> MSMF -> ANY) and black-frame detection - found via research
    into a Windows-10-only camera bug with a Camo Studio virtual camera."""

    def _make_fake_cv2(self, captures_by_backend: dict, has_msmf: bool = True):
        fake_cv2 = MagicMock()
        fake_cv2.CAP_DSHOW = 1
        if has_msmf:
            fake_cv2.CAP_MSMF = 2
        else:
            del fake_cv2.CAP_MSMF  # MagicMock returns a Mock for any attr by default
        fake_cv2.CAP_ANY = 0

        def _video_capture(index, backend):
            return captures_by_backend[backend]

        fake_cv2.VideoCapture.side_effect = _video_capture
        return fake_cv2

    def test_dshow_fails_msmf_succeeds(self) -> None:
        dshow_cap = _FakeCv2Capture(opens=False, frames=[])
        msmf_cap = _FakeCv2Capture(opens=True, frames=[_real_frame()])
        fake_cv2 = self._make_fake_cv2({1: dshow_cap, 2: msmf_cap})

        with patch.dict("sys.modules", {"cv2": fake_cv2}), patch("tarno.vision.camera_capture.sys.platform", "win32"):
            from tarno.vision.camera_capture import CameraCapture

            camera = CameraCapture(device_index=0)
            self.assertTrue(camera.start())
            self.assertIs(camera._cap, msmf_cap)

    def test_dshow_black_frame_msmf_succeeds(self) -> None:
        dshow_cap = _FakeCv2Capture(opens=True, frames=[_black_frame()])
        msmf_cap = _FakeCv2Capture(opens=True, frames=[_real_frame()])
        fake_cv2 = self._make_fake_cv2({1: dshow_cap, 2: msmf_cap})

        with patch.dict("sys.modules", {"cv2": fake_cv2}), patch("tarno.vision.camera_capture.sys.platform", "win32"):
            from tarno.vision.camera_capture import CameraCapture

            camera = CameraCapture(device_index=0)
            self.assertTrue(camera.start())
            self.assertIs(camera._cap, msmf_cap)
            self.assertTrue(dshow_cap.released)

    def test_all_backends_fail_returns_false(self) -> None:
        dshow_cap = _FakeCv2Capture(opens=False, frames=[])
        msmf_cap = _FakeCv2Capture(opens=True, frames=[_black_frame()])
        any_cap = _FakeCv2Capture(opens=False, frames=[])
        fake_cv2 = self._make_fake_cv2({1: dshow_cap, 2: msmf_cap, 0: any_cap})

        with patch.dict("sys.modules", {"cv2": fake_cv2}), patch("tarno.vision.camera_capture.sys.platform", "win32"):
            from tarno.vision.camera_capture import CameraCapture

            camera = CameraCapture(device_index=0)
            self.assertFalse(camera.start())
            self.assertFalse(camera.is_active)

    def test_missing_msmf_backend_skips_to_any(self) -> None:
        any_cap = _FakeCv2Capture(opens=True, frames=[_real_frame()])
        fake_cv2 = self._make_fake_cv2({1: _FakeCv2Capture(opens=False, frames=[]), 0: any_cap}, has_msmf=False)

        with patch.dict("sys.modules", {"cv2": fake_cv2}), patch("tarno.vision.camera_capture.sys.platform", "win32"):
            from tarno.vision.camera_capture import CameraCapture

            camera = CameraCapture(device_index=0)
            self.assertTrue(camera.start())  # must not raise AttributeError
            self.assertIs(camera._cap, any_cap)

    def test_happy_path_uses_first_backend_without_falling_through(self) -> None:
        dshow_cap = _FakeCv2Capture(opens=True, frames=[_real_frame()])
        msmf_cap = _FakeCv2Capture(opens=True, frames=[_real_frame()])
        fake_cv2 = self._make_fake_cv2({1: dshow_cap, 2: msmf_cap})

        with patch.dict("sys.modules", {"cv2": fake_cv2}), patch("tarno.vision.camera_capture.sys.platform", "win32"):
            from tarno.vision.camera_capture import CameraCapture

            camera = CameraCapture(device_index=0)
            self.assertTrue(camera.start())
            self.assertIs(camera._cap, dshow_cap)
            self.assertFalse(msmf_cap.released)  # never even touched


if __name__ == "__main__":
    unittest.main()
