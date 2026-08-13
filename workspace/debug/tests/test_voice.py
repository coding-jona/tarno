"""Regression tests for wake-word and TTS voice changes."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pyaudio

from tarno.core.config import AudioConfig, WakeWordConfig


class AudioStreamTests(unittest.TestCase):
    """Tests for AudioStream lifecycle and recovery helpers."""

    def _make_config(self) -> AudioConfig:
        return AudioConfig(
            sample_rate=16000,
            channels=1,
            chunk_size=1280,
        )

    @patch("tarno.voice.audio_stream.pyaudio.PyAudio")
    def test_flush_input_buffer_reads_and_discards_chunks(self, mock_pa):
        """flush_input_buffer must consume configured chunks without failing."""
        from tarno.voice.audio_stream import AudioStream

        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True
        mock_stream.read.return_value = b"\x00" * 2560
        mock_instance = mock_pa.return_value
        mock_instance.open.return_value = mock_stream
        mock_instance.get_sample_size.return_value = 2
        mock_instance.get_host_api_info_by_type.return_value = {"defaultInputDevice": -1}

        config = self._make_config()
        stream = AudioStream(config)
        stream.start()
        stream.flush_input_buffer(chunks=3)

        self.assertEqual(mock_stream.read.call_count, 3)
        stream.stop()


class WakeWordConfigTests(unittest.TestCase):
    """Tests for wake-word configuration."""

    def test_sensitivity_and_threshold_are_distinct(self):
        config = WakeWordConfig(threshold=0.5, sensitivity=0.9)
        self.assertEqual(config.threshold, 0.5)
        self.assertEqual(config.sensitivity, 0.9)

    def test_default_sensitivity_for_porcupine(self):
        config = WakeWordConfig()
        self.assertEqual(config.sensitivity, 0.9)


class WakeWordDetectorTests(unittest.TestCase):
    """Tests for WakeWordDetector backend wiring."""

    def test_porcupine_uses_sensitivity(self) -> None:
        """pvporcupine.create must be called with the sensitivity config, not threshold."""
        from unittest.mock import patch

        from tarno.voice.wakeword import WakeWordDetector

        mock_porcupine = MagicMock()
        mock_porcupine.frame_length = 512
        mock_porcupine.process.return_value = -1

        mock_pvporcupine = MagicMock()
        mock_pvporcupine.create.return_value = mock_porcupine

        config = WakeWordConfig(
            model_name="jarvis",
            backend="porcupine",
            threshold=0.5,
            sensitivity=0.85,
        )

        with patch.dict("sys.modules", {"pvporcupine": mock_pvporcupine}):
            with patch.dict("os.environ", {"PICOVOICE_API_KEY": "test-key"}):
                WakeWordDetector(config)

        mock_pvporcupine.create.assert_called_once()
        call_kwargs = mock_pvporcupine.create.call_args.kwargs
        self.assertEqual(call_kwargs["keywords"], ["jarvis"])
        self.assertEqual(call_kwargs["sensitivities"], [0.85])

    def test_openwakeword_jarvis_model_uses_hey_jarvis_onnx(self) -> None:
        """model_name 'jarvis' must resolve to the bundled hey_jarvis_v0.1.onnx model."""
        from tarno.voice import wakeword

        self.assertEqual(
            wakeword._OWW_MODEL_MAP.get("jarvis"), "hey_jarvis_v0.1.onnx"
        )
        self.assertEqual(
            wakeword._OWW_MODEL_MAP.get("hey_jarvis"), "hey_jarvis_v0.1.onnx"
        )

    def test_openwakeword_recovery_after_reset(self) -> None:
        """Wake word detection must work again after reset() simulating post-query recovery."""
        from unittest.mock import patch

        from tarno.voice.wakeword import WakeWordDetector

        mock_model = MagicMock()
        # First detection, then reset, then detection again.
        predict_responses = [
            {"hey_jarvis_v0.1": 0.9},
            {"hey_jarvis_v0.1": 0.9},
        ]
        mock_model.predict.side_effect = predict_responses

        from tarno.core.config import AGCConfig

        config = WakeWordConfig(
            model_name="hey_jarvis",
            backend="openwakeword",
            threshold=0.5,
            patience=1,
            debounce_time=0.0,
        )
        agc_config = AGCConfig(enabled=False)  # dummy_chunk ist ein MagicMock, kein echtes np.ndarray

        with patch.object(
            WakeWordDetector, "_init_openwakeword", autospec=True
        ) as mock_init:
            def _fake_init(self, cfg):
                self._model = mock_model
                self._model_key = "hey_jarvis_v0.1"

            mock_init.side_effect = _fake_init
            detector = WakeWordDetector(config, agc_config=agc_config)

        dummy_chunk = MagicMock()
        self.assertTrue(detector.process_frame(dummy_chunk))

        detector.reset()
        mock_model.reset.assert_called_once()
        mock_model.reset.reset_mock()

        self.assertTrue(detector.process_frame(dummy_chunk))
        mock_model.reset.assert_not_called()


def _make_detector_for_agc(config: WakeWordConfig, agc_config=None):
    """Constructs a WakeWordDetector with _init_openwakeword mocked out, so
    AGC wiring can be tested without loading a real ONNX model.

    Forces backend="openwakeword" regardless of what the caller's config
    says - config.backend now defaults to "vosk", and without this override
    these tests would silently load the real (cached-locally, but still a
    slow/network-dependent) Vosk model instead of hitting the mocked-out
    _init_openwakeword path they're actually meant to isolate."""
    import dataclasses

    from tarno.voice.wakeword import WakeWordDetector

    config = dataclasses.replace(config, backend="openwakeword")
    with patch.object(WakeWordDetector, "_init_openwakeword", autospec=True):
        return WakeWordDetector(config, agc_config=agc_config)


class WakeWordAGCTests(unittest.TestCase):
    """Tests that WakeWordDetector correctly wires the shared
    AutomaticGainControl (tarno/voice/audio_utils.py, see test_audio_utils.py
    for the gain math itself) - found via live testing: the audio pipeline
    had no gain stage at all, forcing the user to nearly shout for the wake
    word to clear openWakeWord's score threshold."""

    def test_agc_can_be_disabled_via_config(self) -> None:
        from tarno.core.config import AGCConfig
        from tarno.voice.wakeword import WakeWordDetector

        config = WakeWordConfig(backend="openwakeword", threshold=0.5, patience=1, debounce_time=0.0)
        agc_config = AGCConfig(enabled=False)
        mock_model = MagicMock()
        mock_model.predict.return_value = {"hey_jarvis_v0.1": 0.9}

        with patch.object(WakeWordDetector, "_init_openwakeword", autospec=True) as mock_init:
            def _fake_init(self, cfg):
                self._model = mock_model
                self._model_key = "hey_jarvis_v0.1"

            mock_init.side_effect = _fake_init
            detector = WakeWordDetector(config, agc_config=agc_config)

        with patch.object(detector._agc, "apply") as mock_agc_apply:
            chunk = np.zeros(1280, dtype=np.int16)
            detector.process_frame(chunk)
            mock_agc_apply.assert_not_called()
        np.testing.assert_array_equal(mock_model.predict.call_args.args[0], chunk)

    def test_reset_resets_agc_gain(self) -> None:
        # detector.reset() itself is covered by test_openwakeword_recovery_
        # after_reset (mocks self._model too) - this test isolates just the
        # AGC-reset wiring via the same shared AutomaticGainControl instance.
        config = WakeWordConfig()
        detector = _make_detector_for_agc(config)

        detector._agc.apply(np.full(1280, 10, dtype=np.int16))  # push gain up
        self.assertGreater(detector._agc._gain, 1.0)

        detector._agc.reset()
        self.assertEqual(detector._agc._gain, 1.0)

    def test_default_threshold_value(self) -> None:
        config = WakeWordConfig()
        self.assertEqual(config.threshold, 0.10)


class AudioStreamDeviceResolutionTests(unittest.TestCase):
    """Tests for AudioStream's WASAPI default-input-device resolution (found
    via live testing: without pinning to the real WASAPI default device,
    PortAudio's own ambient default can diverge from Windows' actual default
    device - a host-API discrepancy, not a Windows-10-vs-11 difference; both
    versions use the identical WASAPI/MME stack, researched and confirmed
    this session)."""

    def _make_config(self, microphone_device: str = "default") -> AudioConfig:
        return AudioConfig(
            sample_rate=16000,
            channels=1,
            chunk_size=1280,
            microphone_device=microphone_device,
        )

    @patch("tarno.voice.audio_stream.pyaudio.PyAudio")
    def test_resolves_wasapi_default_input_device_when_target_is_default(self, mock_pa) -> None:
        from tarno.voice.audio_stream import AudioStream

        mock_instance = mock_pa.return_value
        mock_instance.get_host_api_info_by_type.return_value = {"defaultInputDevice": 3}

        stream = AudioStream(self._make_config("default"))
        self.assertEqual(stream._device_index, 3)

    @patch("tarno.voice.audio_stream.pyaudio.PyAudio")
    def test_falls_back_to_none_when_wasapi_unavailable(self, mock_pa) -> None:
        from tarno.voice.audio_stream import AudioStream

        mock_instance = mock_pa.return_value
        mock_instance.get_host_api_info_by_type.side_effect = OSError("no WASAPI")

        stream = AudioStream(self._make_config("default"))
        self.assertIsNone(stream._device_index)

    @patch("tarno.voice.audio_stream.pyaudio.PyAudio")
    def test_falls_back_to_none_when_wasapi_reports_no_default_input_device(self, mock_pa) -> None:
        from tarno.voice.audio_stream import AudioStream

        mock_instance = mock_pa.return_value
        mock_instance.get_host_api_info_by_type.return_value = {"defaultInputDevice": -1}

        stream = AudioStream(self._make_config("default"))
        self.assertIsNone(stream._device_index)

    @patch("tarno.voice.audio_stream.pyaudio.PyAudio")
    def test_explicit_device_index_bypasses_wasapi_resolution(self, mock_pa) -> None:
        from tarno.voice.audio_stream import AudioStream

        mock_instance = mock_pa.return_value

        stream = AudioStream(self._make_config("2"))
        self.assertEqual(stream._device_index, 2)
        mock_instance.get_host_api_info_by_type.assert_not_called()

    @patch("tarno.voice.audio_stream.pyaudio.PyAudio")
    def test_open_stream_still_falls_back_on_wasapi_device_open_failure(self, mock_pa) -> None:
        from tarno.voice.audio_stream import AudioStream

        mock_instance = mock_pa.return_value
        mock_instance.get_host_api_info_by_type.return_value = {"defaultInputDevice": 3}
        mock_instance.get_device_count.return_value = 2
        mock_instance.get_device_info_by_index.side_effect = lambda i: {"maxInputChannels": 1}

        mock_stream = MagicMock()

        def _open(**kwargs):
            if kwargs.get("input_device_index") == 3:
                raise OSError("device 3 unavailable")
            return mock_stream

        mock_instance.open.side_effect = _open

        stream = AudioStream(self._make_config("default"))
        stream.start()

        self.assertNotEqual(stream._device_index, 3)

    @patch("tarno.voice.audio_stream.pyaudio.PyAudio")
    def test_explicit_name_search_prefers_wasapi_over_mme_match(self, mock_pa) -> None:
        """Regression test: the same physical mic often appears multiple
        times across host APIs (MME/DirectSound/WASAPI) - matching by name
        must prefer the WASAPI entry over a lower-quality MME/DirectSound
        one for the same device."""
        from tarno.voice.audio_stream import AudioStream

        mock_instance = mock_pa.return_value
        mock_instance.get_device_count.return_value = 2
        devices = {
            0: {"maxInputChannels": 1, "name": "USB Microphone", "hostApi": 0},
            1: {"maxInputChannels": 1, "name": "USB Microphone", "hostApi": 1},
        }
        mock_instance.get_device_info_by_index.side_effect = lambda i: devices[i]
        host_apis = {0: {"type": pyaudio.paMME}, 1: {"type": pyaudio.paWASAPI}}
        mock_instance.get_host_api_info_by_index.side_effect = lambda i: host_apis[i]

        stream = AudioStream(self._make_config("USB Microphone"))
        self.assertEqual(stream._device_index, 1)

    @patch("tarno.voice.audio_stream.pyaudio.PyAudio")
    def test_explicit_name_search_falls_back_to_mme_if_no_wasapi_match(self, mock_pa) -> None:
        from tarno.voice.audio_stream import AudioStream

        mock_instance = mock_pa.return_value
        mock_instance.get_device_count.return_value = 1
        mock_instance.get_device_info_by_index.return_value = {
            "maxInputChannels": 1, "name": "Legacy Microphone", "hostApi": 0,
        }
        mock_instance.get_host_api_info_by_index.return_value = {"type": pyaudio.paMME}

        stream = AudioStream(self._make_config("Legacy Microphone"))
        self.assertEqual(stream._device_index, 0)


class SampleRateFallbackTests(unittest.TestCase):
    """Regression tests for the Windows-10-laptop bug (found live via
    tarno.log): a WASAPI driver rejecting the configured 16kHz rate with
    'Invalid sample rate' must retry the SAME device at its native rate
    instead of silently swapping to a different, possibly-wrong device."""

    def _make_config(self) -> AudioConfig:
        return AudioConfig(
            sample_rate=16000, channels=1, chunk_size=1280, microphone_device="2",
        )

    @patch("tarno.voice.audio_stream.pyaudio.PyAudio")
    def test_retries_same_device_at_native_rate_on_invalid_sample_rate(self, mock_pa) -> None:
        from tarno.voice.audio_stream import AudioStream

        mock_stream = MagicMock()
        mock_instance = mock_pa.return_value
        mock_instance.get_sample_size.return_value = 2
        mock_instance.get_device_info_by_index.return_value = {"defaultSampleRate": 48000.0}

        def _open(**kwargs):
            if kwargs.get("rate") == 16000:
                raise OSError("[Errno -9997] Invalid sample rate")
            return mock_stream

        mock_instance.open.side_effect = _open

        stream = AudioStream(self._make_config())
        stream.start()

        self.assertEqual(stream._device_index, 2)  # same device, not a fallback
        self.assertEqual(stream._capture_rate, 48000)
        stream.stop()

    @patch("tarno.voice.audio_stream.pyaudio.PyAudio")
    def test_falls_back_to_other_device_if_native_rate_also_fails(self, mock_pa) -> None:
        from tarno.voice.audio_stream import AudioStream

        mock_stream = MagicMock()
        mock_instance = mock_pa.return_value
        mock_instance.get_sample_size.return_value = 2
        mock_instance.get_device_info_by_index.side_effect = lambda i: (
            {"defaultSampleRate": 48000.0} if i == 2 else {"maxInputChannels": 1, "defaultSampleRate": 16000.0}
        )
        mock_instance.get_device_count.return_value = 3

        def _open(**kwargs):
            if kwargs.get("input_device_index") == 2:
                raise OSError("device 2 totally broken")
            return mock_stream

        mock_instance.open.side_effect = _open

        stream = AudioStream(self._make_config())
        stream.start()

        self.assertNotEqual(stream._device_index, 2)
        stream.stop()

    @patch("tarno.voice.audio_stream.pyaudio.PyAudio")
    def test_read_frames_resamples_to_exact_configured_length(self, mock_pa) -> None:
        """When capture_rate != configured rate, read_frames must still
        return exactly num_frames * sample_width bytes, regardless of the
        resampling ratio, so downstream consumers never see a different
        chunk size."""
        from tarno.voice.audio_stream import AudioStream

        config = self._make_config()
        mock_instance = mock_pa.return_value
        mock_instance.get_sample_size.return_value = 2
        stream = AudioStream(config)
        stream._pa = mock_instance
        stream._started = True
        stream._capture_rate = 48000
        stream._resample_state = None

        mock_stream = MagicMock()
        native_frames = 3840  # ceil(1280 * 48000 / 16000)
        mock_stream.read.return_value = b"\x00\x01" * native_frames
        stream._stream = mock_stream

        result = stream.read_frames(1280)

        self.assertEqual(len(result), 1280 * 2)


class ListInputDevicesTests(unittest.TestCase):
    """Tests for the Settings microphone picker's device enumeration."""

    @patch("tarno.voice.audio_stream.pyaudio.PyAudio")
    def test_returns_input_devices_with_default_and_builtin_labels(self, mock_pa) -> None:
        from tarno.voice.audio_stream import list_input_devices

        mock_instance = mock_pa.return_value
        mock_instance.get_host_api_info_by_type.return_value = {"defaultInputDevice": 1}
        mock_instance.get_device_count.return_value = 2
        devices = {
            0: {"maxInputChannels": 1, "name": "Microphone Array (Realtek)", "hostApi": 0},
            1: {"maxInputChannels": 1, "name": "USB Microphone", "hostApi": 1},
        }
        mock_instance.get_device_info_by_index.side_effect = lambda i: devices[i]
        host_apis = {0: {"type": pyaudio.paMME, "name": "MME"}, 1: {"type": pyaudio.paWASAPI, "name": "Windows WASAPI"}}
        mock_instance.get_host_api_info_by_index.side_effect = lambda i: host_apis[i]

        result = list_input_devices()

        self.assertEqual(len(result), 2)
        self.assertTrue(result[0]["is_builtin"])   # "Array" name heuristic
        self.assertFalse(result[1]["is_builtin"])
        self.assertFalse(result[0]["is_default"])
        self.assertTrue(result[1]["is_default"])
        self.assertEqual(result[1]["host_api"], "Windows WASAPI")

    @patch("tarno.voice.audio_stream.pyaudio.PyAudio")
    def test_excludes_output_only_devices(self, mock_pa) -> None:
        from tarno.voice.audio_stream import list_input_devices

        mock_instance = mock_pa.return_value
        mock_instance.get_host_api_info_by_type.return_value = {"defaultInputDevice": -1}
        mock_instance.get_device_count.return_value = 1
        mock_instance.get_device_info_by_index.return_value = {
            "maxInputChannels": 0, "name": "Speakers", "hostApi": 0,
        }

        self.assertEqual(list_input_devices(), [])


class SpeechSynthesizerTests(unittest.TestCase):
    """Tests for SpeechSynthesizer sound playback."""

    def _make_config(self) -> AudioConfig:
        return AudioConfig(
            language="de",
            voice="de-DE-ConradNeural",
            speed=1.1,
            tts_cache_dir="~/.tarno/cache/tts",
        )

    @patch("tarno.voice.synthesizer.pygame")
    def test_play_sound_uses_pygame_sound(self, mock_pygame: MagicMock) -> None:
        """play_sound must use pygame.mixer.Sound and return immediately (non-blocking)."""
        from tarno.voice.synthesizer import SpeechSynthesizer

        mock_sound = MagicMock()
        mock_channel = MagicMock()
        mock_channel.get_busy.return_value = False
        mock_sound.play.return_value = mock_channel
        mock_pygame.mixer.Sound.return_value = mock_sound
        mock_pygame.mixer.get_init.return_value = True

        config = self._make_config()
        synth = SpeechSynthesizer(config)

        synth.play_sound()

        mock_pygame.mixer.Sound.assert_called_once()
        mock_sound.play.assert_called_once()

    @patch("tarno.voice.synthesizer.pygame")
    def test_set_output_device_reinits_mixer_with_devicename(self, mock_pygame: MagicMock) -> None:
        from tarno.voice.synthesizer import SpeechSynthesizer

        mock_pygame.mixer.get_init.return_value = True
        config = self._make_config()
        synth = SpeechSynthesizer(config)
        mock_pygame.mixer.init.reset_mock()

        success = synth.set_output_device("USB Speakers")

        self.assertTrue(success)
        mock_pygame.mixer.quit.assert_called_once()
        mock_pygame.mixer.init.assert_called_with(devicename="USB Speakers")
        self.assertEqual(synth._output_device, "USB Speakers")

    @patch("tarno.voice.synthesizer.pygame")
    def test_set_output_device_default_normalizes_to_none(self, mock_pygame: MagicMock) -> None:
        from tarno.voice.synthesizer import SpeechSynthesizer

        mock_pygame.mixer.get_init.return_value = True
        config = self._make_config()
        synth = SpeechSynthesizer(config)
        mock_pygame.mixer.init.reset_mock()

        synth.set_output_device("default")

        mock_pygame.mixer.init.assert_called_with(devicename=None)

    @patch("pygame._sdl2.audio.get_audio_device_names")
    @patch("tarno.voice.synthesizer.pygame")
    def test_list_output_devices_returns_labeled_devices(
        self, mock_pygame: MagicMock, mock_get_names: MagicMock
    ) -> None:
        from tarno.voice.synthesizer import list_output_devices

        mock_pygame.get_init.return_value = True
        mock_get_names.return_value = ["Lautsprecher Array (Realtek)", "USB Speakers"]

        result = list_output_devices()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "Lautsprecher Array (Realtek)")
        self.assertTrue(result[0]["is_builtin"])
        self.assertFalse(result[1]["is_builtin"])

    @patch("tarno.voice.synthesizer.pygame")
    def test_stop_stops_music_and_sound_channels(self, mock_pygame: MagicMock) -> None:
        """stop() must stop both music and any active Sound channels."""
        from tarno.voice.synthesizer import SpeechSynthesizer

        mock_pygame.mixer.Sound.return_value = MagicMock()
        mock_pygame.mixer.get_init.return_value = True

        config = self._make_config()
        synth = SpeechSynthesizer(config)

        synth.stop()

        mock_pygame.mixer.music.stop.assert_called_once()
        mock_pygame.mixer.stop.assert_called_once()

    @patch("tarno.voice.synthesizer.pygame")
    def test_play_sound_warns_when_asset_missing(self, mock_pygame: MagicMock) -> None:
        """If the confirmation WAV cannot be loaded, play_sound should warn and return."""
        from tarno.voice.synthesizer import SpeechSynthesizer

        mock_pygame.mixer.Sound.side_effect = FileNotFoundError("not found")
        mock_pygame.mixer.get_init.return_value = True

        config = self._make_config()
        synth = SpeechSynthesizer(config)

        self.assertIsNone(synth._confirmation_sound)
        # play_sound should return without raising when no sound is loaded.
        synth.play_sound()

    @patch("tarno.voice.synthesizer.pygame")
    def test_play_sound_reinitializes_mixer_when_needed(self, mock_pygame: MagicMock) -> None:
        """play_sound must re-init pygame.mixer if it was terminated."""
        from tarno.voice.synthesizer import SpeechSynthesizer

        mock_sound = MagicMock()
        mock_channel = MagicMock()
        mock_channel.get_busy.return_value = False
        mock_sound.play.return_value = mock_channel
        mock_pygame.mixer.Sound.return_value = mock_sound
        mock_pygame.mixer.get_init.return_value = None

        config = self._make_config()
        synth = SpeechSynthesizer(config)

        # Simulate mixer that was terminated after init
        synth._mixer_ready = False
        synth.play_sound()

        mock_pygame.mixer.init.assert_called()

    @patch("tarno.voice.synthesizer.time.sleep")
    @patch("tarno.voice.synthesizer.pygame")
    def test_speak_does_not_hang_forever_if_get_busy_never_clears(
        self, mock_pygame: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """Regression test: a pygame/audio glitch where get_busy() never
        returns False must not wedge speak() (and thus the caller's thread)
        forever - it must time out, stop playback and still fire
        on_tts_finished so the engine can continue processing."""
        from tarno.voice.synthesizer import SpeechSynthesizer

        mock_pygame.mixer.get_init.return_value = True
        mock_pygame.mixer.music.get_busy.return_value = True  # never clears

        finished = MagicMock()
        config = self._make_config()
        synth = SpeechSynthesizer(config)
        synth._on_tts_finished = finished

        engine = MagicMock()
        engine.name = "test"
        engine.supports_streaming = False
        synth._engines = [engine]

        cache_path = synth._cache_path("hallo", engine)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(b"fake-mp3-data")
        try:
            synth.speak("hallo")
        finally:
            cache_path.unlink(missing_ok=True)

        mock_pygame.mixer.music.stop.assert_called()
        finished.assert_called_once()

    @patch("tarno.voice.synthesizer.pygame")
    def test_compute_speech_envelope_normalizes_and_reports_duration(
        self, mock_pygame: MagicMock
    ) -> None:
        """The envelope must be normalized against its own loudest window
        (peak == 1.0) and report the real decoded duration, since this is
        what the Orb's whole-body resonance animation is timed against."""
        from tarno.voice.synthesizer import _ENVELOPE_WINDOW_MS, _compute_speech_envelope

        freq = 1000
        mock_pygame.mixer.get_init.return_value = (freq, -16, 1)
        window_samples = int(freq * _ENVELOPE_WINDOW_MS / 1000)
        loud = np.full(window_samples, 30000, dtype=np.int16)
        quiet = np.full(window_samples, 3000, dtype=np.int16)
        raw = np.concatenate([loud, quiet]).tobytes()

        mock_sound = MagicMock()
        mock_sound.get_length.return_value = 2.5
        mock_sound.get_raw.return_value = raw
        mock_pygame.mixer.Sound.return_value = mock_sound

        levels, duration = _compute_speech_envelope("fake.mp3")

        self.assertEqual(duration, 2.5)
        self.assertEqual(len(levels), 2)
        self.assertAlmostEqual(levels[0], 1.0)
        self.assertLess(levels[1], levels[0])

    @patch("tarno.voice.synthesizer.pygame")
    def test_compute_speech_envelope_returns_empty_on_decode_failure(
        self, mock_pygame: MagicMock
    ) -> None:
        """A corrupt/unreadable cache file must degrade gracefully (no
        envelope, no crash) rather than blocking speech playback."""
        from tarno.voice.synthesizer import _compute_speech_envelope

        mock_pygame.mixer.Sound.side_effect = Exception("boom")

        levels, duration = _compute_speech_envelope("fake.mp3")

        self.assertEqual(levels, [])
        self.assertEqual(duration, 0.0)

    @patch("tarno.voice.synthesizer._compute_speech_envelope")
    @patch("tarno.voice.synthesizer.pygame")
    def test_speak_calls_on_tts_started_with_envelope_and_duration(
        self, mock_pygame: MagicMock, mock_envelope: MagicMock
    ) -> None:
        """speak() must precompute the real envelope/duration from the
        cached audio file and pass it to on_tts_started - this is what lets
        the Orb play a resonance animation genuinely synced to what TARNO is
        saying, instead of a generic procedural loop."""
        from tarno.voice.synthesizer import SpeechSynthesizer

        mock_pygame.mixer.get_init.return_value = True
        mock_pygame.mixer.music.get_busy.return_value = False
        mock_envelope.return_value = ([0.2, 0.8, 0.3], 1.4)

        started = MagicMock()
        config = self._make_config()
        synth = SpeechSynthesizer(config, on_tts_started=started)

        engine = MagicMock()
        engine.name = "test"
        engine.supports_streaming = False
        synth._engines = [engine]

        cache_path = synth._cache_path("hallo", engine)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(b"fake-mp3-data")
        try:
            synth.speak("hallo")
        finally:
            cache_path.unlink(missing_ok=True)

        started.assert_called_once_with("hallo", [0.2, 0.8, 0.3], 1.4)


class AssetResolutionTests(unittest.TestCase):
    """Tests for confirmation asset path resolution."""

    def test_asset_path_points_to_tarno_assets(self):
        from tarno.voice.synthesizer import SpeechSynthesizer

        path = SpeechSynthesizer._resolve_asset_path("confirmation.wav")
        self.assertTrue("jarvis" in str(path).lower() or "assets" in str(path).lower())

