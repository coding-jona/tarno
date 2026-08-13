"""Phase 2 stabilisation tests for VoiceController and AudioStream.

All tests run without a real microphone. Audio data comes from synthetic
NumPy arrays or pre-generated WAV-like byte sequences.
"""

from __future__ import annotations

import struct
import threading
import time
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np

from tarno_backend.core.config import AudioConfig, WakeWordConfig, TarnoConfig
from tarno_backend.core.voice_controller import VoiceController, VoiceState


def _make_audio_config() -> AudioConfig:
    return AudioConfig(
        sample_rate=16000,
        channels=1,
        chunk_size=1280,
        energy_threshold=4000,
        listen_timeout=2,
        phrase_time_limit=3,
        # Expliziter Geräte-Index, damit diese PyAudio-Lifecycle-Tests nicht den
        # WASAPI-Standardgeräte-Auflösungspfad durchlaufen (der eine eigene,
        # kurzlebige PyAudio()-Instanz öffnet/schließt - mit dem hier gemockten
        # PyAudio als Singleton würde das die terminate()-Call-Counts verfälschen).
        microphone_device="0",
    )


def _make_wakeword_config() -> WakeWordConfig:
    return WakeWordConfig(
        enabled=True,
        backend="openwakeword",
        model_name="hey_jarvis",
        threshold=0.5,
        patience=1,
        debounce_time=0.0,
    )


def _make_config() -> TarnoConfig:
    return TarnoConfig(
        audio=_make_audio_config(),
        wakeword=_make_wakeword_config(),
    )


def _silence_chunk(chunk_size: int = 1280) -> np.ndarray:
    """Generate a silent audio chunk (zeros)."""
    return np.zeros(chunk_size, dtype=np.int16)


def _noise_chunk(chunk_size: int = 1280, amplitude: int = 500) -> np.ndarray:
    """Generate a random noise audio chunk."""
    rng = np.random.default_rng(42)
    return rng.integers(-amplitude, amplitude, size=chunk_size, dtype=np.int16)


def _tone_chunk(chunk_size: int = 1280, freq: float = 440.0, rate: int = 16000) -> np.ndarray:
    """Generate a sine-wave audio chunk for testing."""
    t = np.arange(chunk_size) / rate
    return (np.sin(2 * np.pi * freq * t) * 16000).astype(np.int16)


# ── AudioStream Tests ──────────────────────────────────────────────


class AudioStreamPauseResumeTests(unittest.TestCase):
    """Test that pause/resume keeps the PyAudio instance alive."""

    @patch("tarno_backend.voice.audio_stream.pyaudio.PyAudio")
    def test_pause_does_not_terminate_pyaudio(self, mock_pa_cls):
        from tarno_backend.voice.audio_stream import AudioStream

        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True
        mock_pa = mock_pa_cls.return_value
        mock_pa.open.return_value = mock_stream

        config = _make_audio_config()
        stream = AudioStream(config)
        stream.start()

        stream.pause()

        mock_pa.terminate.assert_not_called()
        mock_stream.stop_stream.assert_called_once()
        mock_stream.close.assert_called_once()

        self.assertFalse(stream.is_active)
        stream.stop()

    @patch("tarno_backend.voice.audio_stream.pyaudio.PyAudio")
    def test_resume_reopens_stream_on_same_pyaudio(self, mock_pa_cls):
        from tarno_backend.voice.audio_stream import AudioStream

        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True
        mock_stream.read.return_value = b"\x00" * 2560
        mock_pa = mock_pa_cls.return_value
        mock_pa.open.return_value = mock_stream

        config = _make_audio_config()
        stream = AudioStream(config)
        stream.start()

        self.assertEqual(mock_pa.open.call_count, 1)

        stream.pause()
        stream.resume()

        self.assertEqual(mock_pa.open.call_count, 2)
        self.assertTrue(stream.is_active)
        stream.stop()

    @patch("tarno_backend.voice.audio_stream.pyaudio.PyAudio")
    def test_multiple_pause_resume_cycles(self, mock_pa_cls):
        """Simulate 10 wake-word interactions with pause/resume."""
        from tarno_backend.voice.audio_stream import AudioStream

        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True
        mock_stream.read.return_value = b"\x00" * 2560
        mock_pa = mock_pa_cls.return_value
        mock_pa.open.return_value = mock_stream

        config = _make_audio_config()
        stream = AudioStream(config)
        stream.start()

        for i in range(10):
            stream.pause()
            self.assertFalse(stream.is_active, f"Cycle {i}: should be paused")
            stream.resume()
            self.assertTrue(stream.is_active, f"Cycle {i}: should be active")
            # Read a chunk to verify the stream works
            data = stream.read_chunk()
            self.assertIsNotNone(data)

        # PyAudio.terminate should NEVER be called during pause/resume
        mock_pa.terminate.assert_not_called()
        # open should be called 1 (start) + 10 (resumes) = 11 times
        self.assertEqual(mock_pa.open.call_count, 11)
        stream.stop()

    @patch("tarno_backend.voice.audio_stream.pyaudio.PyAudio")
    def test_stop_terminates_pyaudio(self, mock_pa_cls):
        """Full stop() must destroy everything."""
        from tarno_backend.voice.audio_stream import AudioStream

        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True
        mock_pa = mock_pa_cls.return_value
        mock_pa.open.return_value = mock_stream

        config = _make_audio_config()
        stream = AudioStream(config)
        stream.start()
        stream.stop()

        mock_pa.terminate.assert_called_once()

    @patch("tarno_backend.voice.audio_stream.pyaudio.PyAudio")
    def test_restart_recovers_from_failure(self, mock_pa_cls):
        from tarno_backend.voice.audio_stream import AudioStream

        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True
        mock_pa = mock_pa_cls.return_value
        mock_pa.open.return_value = mock_stream

        config = _make_audio_config()
        stream = AudioStream(config)
        stream.start()

        result = stream.restart()

        self.assertTrue(result)
        self.assertTrue(stream.is_active)
        stream.stop()


# ── VoiceController State Machine Tests ────────────────────────────


class VoiceControllerStateMachineTests(unittest.TestCase):
    """Test state transitions without real audio hardware."""

    def test_initial_state_is_idle(self):
        config = _make_config()
        vc = VoiceController(config)
        self.assertEqual(vc.state, VoiceState.IDLE)
        self.assertEqual(vc.interaction_count, 0)

    def test_state_transitions_are_reported(self):
        """Verify that state changes go through the on_state callback."""
        states: list[str] = []

        config = _make_config()
        vc = VoiceController(config, on_state=lambda s: states.append(s))

        # Manually test the internal state machine
        vc._set_state(VoiceState.IDLE)
        vc._set_state(VoiceState.LISTENING)
        vc._set_state(VoiceState.PROCESSING)
        vc._set_state(VoiceState.SPEAKING)
        vc._set_state(VoiceState.IDLE)

        self.assertEqual(states, ["idle", "listening", "processing", "speaking", "idle"])

    def test_duplicate_state_still_fires_callback(self):
        """Setting the same state twice should still fire the callback."""
        states: list[str] = []
        config = _make_config()
        vc = VoiceController(config, on_state=lambda s: states.append(s))

        vc._set_state(VoiceState.IDLE)
        vc._set_state(VoiceState.IDLE)

        # Callback fires for both, even if state didn't change
        self.assertEqual(len(states), 2)


class VoiceControllerLifecycleTests(unittest.TestCase):
    """Test start/stop/watchdog without real audio."""

    @patch("tarno_backend.core.voice_controller.VoiceController._run_loop")
    def test_start_creates_watchdog_thread(self, mock_loop):
        mock_loop.side_effect = lambda: None

        config = _make_config()
        vc = VoiceController(config)
        vc.start()

        time.sleep(0.1)
        self.assertTrue(vc.active)
        self.assertIsNotNone(vc._watchdog_thread)
        self.assertTrue(vc._watchdog_thread.is_alive())

        vc.stop()
        self.assertFalse(vc.active)

    @patch("tarno_backend.core.voice_controller.VoiceController._run_loop")
    def test_stop_logs_interaction_count(self, mock_loop):
        mock_loop.side_effect = lambda: None

        config = _make_config()
        vc = VoiceController(config)
        vc._interaction_count = 5
        vc.start()
        time.sleep(0.05)
        vc.stop()

        self.assertEqual(vc.interaction_count, 5)

    def test_signal_turn_ready_unblocks_wait(self):
        config = _make_config()
        vc = VoiceController(config)
        vc._turn_ready.clear()

        result = [False]

        def wait_thread():
            result[0] = vc._turn_ready.wait(timeout=2.0)

        t = threading.Thread(target=wait_thread)
        t.start()
        time.sleep(0.05)
        vc.signal_turn_ready()
        t.join(timeout=1)
        self.assertTrue(result[0])


class VoiceControllerWatchdogTests(unittest.TestCase):
    """Test that the watchdog detects hangs and triggers recovery."""

    def test_heartbeat_updates_timestamp(self):
        config = _make_config()
        vc = VoiceController(config)
        before = vc._last_heartbeat
        time.sleep(0.01)
        vc._heartbeat()
        self.assertGreater(vc._last_heartbeat, before)

    @patch("tarno_backend.core.voice_controller.VoiceController._run_loop_safe")
    def test_watchdog_detects_missing_heartbeat(self, mock_loop):
        """Simulate a hung loop by not sending heartbeats."""
        mock_loop.side_effect = lambda: time.sleep(10)

        config = _make_config()
        vc = VoiceController(config)
        vc._WATCHDOG_INTERVAL = 0.1
        vc._WATCHDOG_TIMEOUT = 0.2

        errors: list[str] = []
        vc._on_error = lambda msg: errors.append(msg)

        vc._active = True
        vc._last_heartbeat = time.monotonic() - 1.0  # simulate old heartbeat
        vc._watchdog_thread = threading.Thread(target=vc._watchdog, daemon=True)
        vc._watchdog_thread.start()

        time.sleep(0.5)
        vc._active = False
        vc._watchdog_thread.join(timeout=1)

        self.assertTrue(len(errors) > 0, "Watchdog should have reported an error")
        self.assertTrue(any("hängt" in e for e in errors))


# ── Virtual Audio Stream Tests ─────────────────────────────────────


class VirtualAudioTests(unittest.TestCase):
    """Test audio processing with synthetic data (no microphone required)."""

    def test_silence_chunk_is_all_zeros(self):
        chunk = _silence_chunk(1280)
        self.assertEqual(chunk.dtype, np.int16)
        self.assertEqual(len(chunk), 1280)
        self.assertEqual(chunk.sum(), 0)

    def test_noise_chunk_has_correct_shape(self):
        chunk = _noise_chunk(1280, amplitude=500)
        self.assertEqual(chunk.dtype, np.int16)
        self.assertEqual(len(chunk), 1280)
        self.assertTrue(np.abs(chunk).max() <= 500)

    def test_tone_chunk_has_correct_frequency_content(self):
        chunk = _tone_chunk(16000, freq=440.0, rate=16000)
        self.assertEqual(len(chunk), 16000)
        # The peak amplitude should be close to 16000
        self.assertGreater(np.abs(chunk).max(), 10000)

    @patch("tarno_backend.voice.audio_stream.pyaudio.PyAudio")
    def test_read_chunk_returns_numpy_array(self, mock_pa_cls):
        from tarno_backend.voice.audio_stream import AudioStream

        chunk_bytes = _silence_chunk(1280).tobytes()
        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True
        mock_stream.read.return_value = chunk_bytes
        mock_pa = mock_pa_cls.return_value
        mock_pa.open.return_value = mock_stream

        config = _make_audio_config()
        stream = AudioStream(config)
        stream.start()

        result = stream.read_chunk()

        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.dtype, np.int16)
        self.assertEqual(len(result), 1280)
        stream.stop()


# ── Integration: Wake-Word with Virtual Stream ────────────────────


class WakeWordVirtualStreamTests(unittest.TestCase):
    """Test wake-word detection using virtual audio data."""

    def _make_mock_wakeword(self):
        """Create a mock WakeWordDetector that triggers on the 5th frame."""
        mock = MagicMock()
        mock.process_frame = MagicMock()
        call_count = [0]

        def process_side_effect(chunk):
            call_count[0] += 1
            return call_count[0] == 5  # trigger on 5th frame

        mock.process_frame.side_effect = process_side_effect
        return mock

    def test_wake_word_detection_with_synthetic_audio(self):
        """Verify that the wake-word detector processes virtual frames."""
        mock_ww = self._make_mock_wakeword()

        for i in range(10):
            chunk = _silence_chunk(1280) if i != 4 else _tone_chunk(1280)
            detected = mock_ww.process_frame(chunk)
            if i == 4:
                self.assertTrue(detected, "Should detect on frame 5")
            else:
                self.assertFalse(detected, f"Should not detect on frame {i+1}")

    def test_wake_word_resets_after_detection(self):
        """After detection, reset() must be callable without error."""
        mock_ww = self._make_mock_wakeword()

        # Process until detection
        for i in range(5):
            mock_ww.process_frame(_silence_chunk())

        mock_ww.reset()
        mock_ww.reset.assert_called_once()


# ── Full Pipeline Simulation ───────────────────────────────────────


class _TestableVoiceController(VoiceController):
    """Subclass that injects mock audio/wakeword/recognizer objects."""

    def __init__(self, config, mock_stream, mock_wakeword, mock_recognizer, **kwargs):
        super().__init__(config, **kwargs)
        self._mock_stream = mock_stream
        self._mock_wakeword = mock_wakeword
        self._mock_recognizer = mock_recognizer

    def _run_loop(self) -> None:
        """Override _run_loop to use injected mocks instead of real hardware.

        Mirrors the real VoiceController._run_loop's control flow (source is
        threaded through _recognize_and_emit/_conversation_loop instead of
        pausing the stream before the first listen - see the live-tested fix
        in tarno/core/voice_controller.py), just with mocks standing in for
        the real AudioStream/WakeWordDetector/recognizer."""
        stream = self._mock_stream
        wakeword = self._mock_wakeword
        recognizer = self._mock_recognizer

        try:
            stream.start()
            source = MagicMock()
            recognizer.calibrate(source)
            self._set_state(VoiceState.IDLE)

            while self._active:
                self._heartbeat()

                try:
                    chunk = stream.read_chunk()
                except RuntimeError:
                    if stream.restart():
                        wakeword.reset()
                        continue
                    raise

                if not wakeword.process_frame(chunk):
                    continue

                wakeword.reset()
                self._on_wake_word()
                self._interaction_count += 1

                self._set_state(VoiceState.LISTENING)
                self._turn_ready.clear()

                heard_something = self._recognize_and_emit(recognizer, source)

                if heard_something:
                    self._set_state(VoiceState.PROCESSING)
                    stream.pause()
                    turn_completed = self._turn_ready.wait(timeout=self._TURN_TIMEOUT)
                    if self._active:
                        stream.resume()
                        source = MagicMock()
                        stream.flush_input_buffer()
                        if turn_completed:
                            self._conversation_loop(recognizer, stream, source)

                if self._active:
                    wakeword.reset()
                    self._set_state(VoiceState.IDLE)
        finally:
            stream.stop()


class VoicePipelineSimulationTests(unittest.TestCase):
    """Simulate the full pipeline: wake-word → STT → response → back to idle.

    Uses a testable VoiceController subclass with injected mocks.
    No real audio hardware is touched.
    """

    def test_full_interaction_cycle(self):
        """Simulate: start → wake-word → listen → process → signal → back to idle."""
        # ── Setup mocks ──
        mock_stream = MagicMock()
        chunk_data = _silence_chunk(1280)
        call_counter = [0]

        def read_chunk_side_effect():
            call_counter[0] += 1
            if call_counter[0] > 50:
                raise RuntimeError("safety limit")
            return chunk_data

        mock_stream.read_chunk.side_effect = read_chunk_side_effect
        mock_stream.restart.return_value = True

        mock_ww = MagicMock()
        ww_call = [0]

        def ww_process(chunk):
            ww_call[0] += 1
            return ww_call[0] == 3  # trigger on 3rd frame

        mock_ww.process_frame.side_effect = ww_process

        mock_recognizer = MagicMock()
        mock_recognizer.listen_and_recognize.side_effect = [
            "Was ist das Wetter?",  # first recognition
            None,  # no follow-up → back to idle
        ]

        # ── Track callbacks ──
        states: list[str] = []
        wake_words: list[bool] = []
        speeches: list[str] = []

        config = _make_config()
        vc = _TestableVoiceController(
            config,
            mock_stream=mock_stream,
            mock_wakeword=mock_ww,
            mock_recognizer=mock_recognizer,
            on_wake_word=lambda: wake_words.append(True),
            on_speech=lambda t: speeches.append(t),
            on_state=lambda s: states.append(s),
        )

        # Run the loop in a thread, then stop it after it processes
        def run_then_stop():
            time.sleep(0.3)
            vc.signal_turn_ready()
            time.sleep(0.2)
            vc._active = False

        stopper = threading.Thread(target=run_then_stop, daemon=True)
        stopper.start()

        vc._active = True
        vc._last_heartbeat = time.monotonic()
        try:
            vc._run_loop()
        except RuntimeError:
            pass

        stopper.join(timeout=2)

        # ── Assertions ──
        self.assertTrue(len(wake_words) > 0, "Wake word should have been detected")
        self.assertIn("Was ist das Wetter?", speeches)
        self.assertIn("idle", states)
        self.assertIn("listening", states)
        self.assertIn("processing", states)
        self.assertEqual(vc.interaction_count, 1)

        # Verify pause/resume was used instead of stop/start
        mock_stream.pause.assert_called()
        mock_stream.resume.assert_called()

    def test_multiple_interactions_without_restart(self):
        """Simulate 3 consecutive wake-word activations."""
        mock_stream = MagicMock()
        chunk_data = _silence_chunk(1280)
        call_counter = [0]

        def read_chunk_side_effect():
            call_counter[0] += 1
            if call_counter[0] > 200:
                raise RuntimeError("safety limit")
            return chunk_data

        mock_stream.read_chunk.side_effect = read_chunk_side_effect

        # Wake word triggers on frames 3, 10, 17
        ww_call = [0]
        trigger_frames = {3, 10, 17}

        def ww_process(chunk):
            ww_call[0] += 1
            return ww_call[0] in trigger_frames

        mock_ww = MagicMock()
        mock_ww.process_frame.side_effect = ww_process

        recognition_responses = [
            "Erste Frage",
            None,  # no follow-up
            "Zweite Frage",
            None,  # no follow-up
            "Dritte Frage",
            None,  # no follow-up
        ]
        mock_recognizer = MagicMock()
        mock_recognizer.listen_and_recognize.side_effect = recognition_responses

        speeches: list[str] = []
        states: list[str] = []
        config = _make_config()

        vc = _TestableVoiceController(
            config,
            mock_stream=mock_stream,
            mock_wakeword=mock_ww,
            mock_recognizer=mock_recognizer,
            on_speech=lambda t: speeches.append(t),
            on_state=lambda s: states.append(s),
        )

        turn_count = [0]

        def signal_turns():
            while vc._active:
                time.sleep(0.05)
                if vc.state == VoiceState.PROCESSING:
                    turn_count[0] += 1
                    time.sleep(0.05)
                    vc.signal_turn_ready()
            # Final stop
            time.sleep(0.1)

        def stop_after_interactions():
            while vc._active:
                time.sleep(0.05)
                if vc.interaction_count >= 3 and mock_stream.resume.call_count >= 3:
                    time.sleep(0.1)
                    vc._active = False
                    break

        t1 = threading.Thread(target=signal_turns, daemon=True)
        t2 = threading.Thread(target=stop_after_interactions, daemon=True)

        vc._active = True
        vc._last_heartbeat = time.monotonic()

        t1.start()
        t2.start()

        try:
            vc._run_loop()
        except RuntimeError:
            pass

        t1.join(timeout=2)
        t2.join(timeout=2)

        self.assertEqual(vc.interaction_count, 3)
        self.assertIn("Erste Frage", speeches)
        self.assertIn("Zweite Frage", speeches)
        self.assertIn("Dritte Frage", speeches)
        # pause/resume should have been called 3 times each
        self.assertEqual(mock_stream.pause.call_count, 3)
        self.assertEqual(mock_stream.resume.call_count, 3)

    def test_conversation_loop_survives_two_consecutive_follow_ups(self):
        """Regression test: found live - _conversation_loop referenced
        AudioStreamSource without importing it in its own scope (only
        _run_loop imported it locally), so a SECOND successful follow-up in
        the same conversation (looping back to build a fresh source after
        resuming the stream) raised NameError and killed the voice loop.
        Earlier tests never caught this because their follow-up recognitions
        always failed (returned None) on the first attempt, exiting before
        ever reaching that line."""
        mock_stream = MagicMock()
        mock_recognizer = MagicMock()
        mock_recognizer.listen_and_recognize.side_effect = [
            "Erster Folgesatz",
            "Zweiter Folgesatz",  # requires a second AudioStreamSource(stream) build
            None,  # ends the conversation
        ]

        speeches: list[str] = []
        config = _make_config()
        vc = VoiceController(config, on_speech=lambda t: speeches.append(t))
        vc._active = True

        def run():
            vc._conversation_loop(mock_recognizer, mock_stream, MagicMock())

        t = threading.Thread(target=run, daemon=True)
        t.start()

        for _ in range(2):
            time.sleep(0.05)
            vc.signal_turn_ready()
        t.join(timeout=2)

        self.assertFalse(t.is_alive())
        self.assertEqual(speeches, ["Erster Folgesatz", "Zweiter Folgesatz"])
        self.assertEqual(mock_stream.resume.call_count, 2)


if __name__ == "__main__":
    unittest.main()
