# `tarno_backend/voice/` — audio pipeline (wake word → STT → TTS)

The full local voice pipeline: microphone capture, wake-word detection,
speech-to-text, text-to-speech, and the safety/quality layers around them.

## Signal flow (roughly, mic → speaker)

1. **`audio_stream.py`**: raw microphone stream, with device fallback if
   the configured input device disappears (TD-021).
2. **`wakeword.py`**: wake-word detection — supports Vosk, openWakeWord, or
   pvporcupine as backend, selected by `wakeword.model_name` in config.
   `model_name: "tarno"` forces the porcupine backend; only genuinely
   openWakeWord-named models use the openWakeWord path.
3. **`vad_silero.py`**: Silero voice-activity detection for streaming.
4. **`adaptive_listener.py`**: listens with a dynamic silence timeout
   instead of a fixed one.
5. Recognition — pick one:
   - **`faster_whisper_recognizer.py`** (primary, local, fast)
   - **`streaming_whisper_recognizer.py`** (streaming variant with a
     volume-threshold VAD)
   - **`recognizer.py`** (Whisper primary with a Google fallback path)
6. **`synthesizer.py`**: text-to-speech output, local engines + streaming +
   fallback; delegates to one of `tts_engines/` (`piper.py`, `edge.py`,
   `neutts.py`).
   - **`piper_synthesizer.py`**: a standalone Piper-only synthesizer
     (older/simpler than the multi-engine `synthesizer.py` — check which
     one is actually wired into `engine.py` before assuming both are live).
7. **`tts_output.py`**: real-time audio output stream for TTS chunks.
8. **`speech_naturalizer.py`**: post-processing so spoken output sounds
   less robotic.
9. **`echo_protection.py`**: prevents TARNO's own TTS output from
   re-triggering the wake word / being transcribed as user speech.

## Supporting

- **`audio_manager.py`**: central device detection/routing decisions.
- **`audio_utils.py`**: shared low-level audio helpers.
- **`permission_manager.py`**: microphone/external-voice-usage permission
  framework.
- **`audit_logger.py`**: audit trail for voice actions and permission/audio
  state changes.
- **`recorder.py`**: local recording with metadata + consent tracking.
- **`voice_reference.py`**: bundled Thorsten-Voice (German) reference
  sample used for voice cloning by engines that support it.
- **`voice_service.py`**: connects mic input to the OVOS message bus
  (used by the `ovos_engine.py` launch mode).

## Cross-references

- State machine + crash recovery/watchdog: `tarno_backend/core/voice_controller.py` (see `core_README.md`)
- Known issues: [`workspace/debug/docs/technical-debt-catalog.md`](../../../workspace/debug/docs/technical-debt-catalog.md) (TD-002 recovery, TD-021 device fallback)
- Standalone debug/calibration tools for this pipeline live in [`workspace/debug/tools/`](../../../workspace/debug/tools/) (`debug_proactive_voice.py`, `vision_calibration.py` is vision not voice — see that folder's own scripts)
