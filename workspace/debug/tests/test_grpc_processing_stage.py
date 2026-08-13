"""Tests that TarnoGrpcBridge broadcasts real ProcessingStageEvents instead of
the old fake, static "Denkt nach..." StatusUpdate that used to fire immediately
on _on_speech(), before any LLM/tool work had actually started.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from tarno_backend.ai.tool_registry import ToolRegistry
from tarno_backend.core.config import TarnoConfig
from tarno_backend.core.events import EventBus, ProcessingStageEvent, SpeechRecognizedEvent, TtsStartedEvent
from tarno_backend.grpc.server import TarnoGrpcBridge


class _FakeEngine:
    def __init__(self) -> None:
        self.config = TarnoConfig()
        self.event_bus = EventBus()
        self.tools = ToolRegistry()


class ProcessingStageWiringTests(unittest.TestCase):
    def test_on_speech_no_longer_broadcasts_fake_status(self) -> None:
        engine = _FakeEngine()
        bridge = TarnoGrpcBridge(engine)
        bridge._broadcast = MagicMock()

        engine.event_bus.publish(SpeechRecognizedEvent(text="Hallo"))

        for call in bridge._broadcast.call_args_list:
            message = call.args[0]
            if message.HasField("status"):
                self.assertNotEqual(message.status.state, "Denkt nach...")

    def test_processing_stage_event_broadcasts_thinking_update(self) -> None:
        engine = _FakeEngine()
        bridge = TarnoGrpcBridge(engine)
        bridge._broadcast = MagicMock()

        engine.event_bus.publish(ProcessingStageEvent(stage="llm_call", detail="Rufe LLM auf..."))

        bridge._broadcast.assert_called_once()
        message = bridge._broadcast.call_args.args[0]
        self.assertTrue(message.HasField("thinking"))
        self.assertTrue(message.thinking.active)
        self.assertEqual(message.thinking.stage, "Rufe LLM auf...")
        self.assertEqual(message.thinking.stage_key, "llm_call")

    def test_tool_exec_stage_key_distinguishable_from_llm_call(self) -> None:
        """Regression test: tool_exec must carry a distinct stage_key from
        llm_call/tool_followup/reasoning, so the client can show "Processing"
        instead of collapsing every stage into one generic "thinking" look."""
        engine = _FakeEngine()
        bridge = TarnoGrpcBridge(engine)
        bridge._broadcast = MagicMock()

        engine.event_bus.publish(ProcessingStageEvent(stage="tool_exec", detail="Führe Tool 'x' aus..."))

        message = bridge._broadcast.call_args.args[0]
        self.assertEqual(message.thinking.stage_key, "tool_exec")

    def test_reasoning_stage_populates_reasoning_field(self) -> None:
        engine = _FakeEngine()
        bridge = TarnoGrpcBridge(engine)
        bridge._broadcast = MagicMock()

        engine.event_bus.publish(ProcessingStageEvent(stage="reasoning", reasoning="kurz überlegt"))

        message = bridge._broadcast.call_args.args[0]
        self.assertEqual(message.thinking.reasoning, "kurz überlegt")

    def test_tts_started_broadcasts_speech_envelope_before_voice_state(self) -> None:
        """The real amplitude envelope must reach the client so the Orb can
        play its whole-body resonance animation - and it must be sent before
        (or alongside) the VOICE_SPEAKING transition, not after, so the
        client already has the data once it enters the "speaking" visual."""
        engine = _FakeEngine()
        bridge = TarnoGrpcBridge(engine)
        bridge._broadcast = MagicMock()

        engine.event_bus.publish(TtsStartedEvent(text="Hallo", envelope=[0.1, 0.9], duration_seconds=1.3))

        calls = bridge._broadcast.call_args_list
        envelope_index = next(i for i, c in enumerate(calls) if c.args[0].HasField("speech_envelope"))
        voice_state_index = next(i for i, c in enumerate(calls) if c.args[0].HasField("voice_state"))
        self.assertLess(envelope_index, voice_state_index)

        envelope_message = calls[envelope_index].args[0]
        levels = list(envelope_message.speech_envelope.levels)
        self.assertEqual(len(levels), 2)
        self.assertAlmostEqual(levels[0], 0.1, places=5)
        self.assertAlmostEqual(levels[1], 0.9, places=5)
        self.assertAlmostEqual(envelope_message.speech_envelope.duration_seconds, 1.3)

    def test_tts_started_without_envelope_skips_speech_envelope_broadcast(self) -> None:
        """No envelope data (e.g. a legacy caller that never computed one)
        must not send an empty/garbage SpeechEnvelopeUpdate."""
        engine = _FakeEngine()
        bridge = TarnoGrpcBridge(engine)
        bridge._broadcast = MagicMock()

        engine.event_bus.publish(TtsStartedEvent(text="Hallo"))

        for call in bridge._broadcast.call_args_list:
            self.assertFalse(call.args[0].HasField("speech_envelope"))


if __name__ == "__main__":
    unittest.main()
