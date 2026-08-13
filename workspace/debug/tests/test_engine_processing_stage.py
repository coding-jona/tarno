"""Tests that TarnoEngine publishes real ProcessingStageEvents during a turn,
replacing the old fake, static "Denkt nach..." placeholder.

TarnoEngine.__init__ is heavy (constructs SpeechSynthesizer, ExtensionCoordinator,
etc.) and no other test in this suite constructs a full instance - this test
bypasses __init__ (object.__new__) and sets only the attributes _process_response
actually touches, matching the lightweight-fake-collaborator pattern already
used in tests/test_core.py's AgentServiceTests.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from tarno_backend.ai.conversation import ConversationManager
from tarno_backend.ai.provider import LLMProvider, LLMResponse, ToolCall
from tarno_backend.ai.tool_registry import ToolDefinition, ToolRegistry
from tarno_backend.core.config import TarnoConfig
from tarno_backend.core.engine import TarnoEngine
from tarno_backend.core.events import ProcessingStageEvent
from tarno_backend.core.permission_service import AutonomyMode


class _FakeToolProvider(LLMProvider):
    """Requests one tool call, then returns a final text response."""

    def __init__(self) -> None:
        self._call = 0

    @property
    def name(self) -> str:
        return "fake_tool"

    @property
    def supports_tools(self) -> bool:
        return True

    def send(self, messages, system, tools=None):
        self._call += 1
        if self._call == 1:
            return LLMResponse(text="", tool_calls=[ToolCall(id="call_1", name="fake", input={})])
        return LLMResponse(text="Erledigt, Sir.", tool_calls=[])

    def send_tool_result(self, messages, system, tools=None):
        return self.send(messages, system, tools)


def _make_bare_engine(provider: LLMProvider) -> TarnoEngine:
    """Constructs a TarnoEngine instance without running __init__, wiring
    only the attributes _process_response touches."""
    engine = object.__new__(TarnoEngine)
    engine.provider = provider
    engine.reasoning_effort = None
    engine.use_high_tier_model = False
    engine.tools = ToolRegistry()
    engine.tools.register(ToolDefinition(
        name="fake",
        description="Fake tool",
        input_schema={"type": "object", "properties": {}},
        handler=lambda: "Fake-Ergebnis",
    ))
    engine.config = TarnoConfig()
    engine._current_chat_id = "default"
    conversation = ConversationManager()
    engine._conversations = {engine._current_chat_id: conversation}
    engine.command_tool = MagicMock()
    engine.command_tool.autonomy_mode = AutonomyMode.ULTIMATE
    engine._active_workspace = None
    engine.event_bus = MagicMock()
    # Kontext-Effizienz (Phase 2/3/5) - _maybe_compress_tool_result und
    # _maybe_publish_context_usage/_maybe_trigger_summarization lesen diese
    # Attribute; normalerweise von TarnoEngine.__init__ gesetzt, hier per
    # bare-engine-Muster manuell nachgezogen.
    engine._context_efficiency_enabled = False
    engine._usage_trackers = {}
    engine._history_summarizer = None
    return engine


class ProcessingStageEventOrderTests(unittest.TestCase):
    def test_tool_call_turn_publishes_stages_in_order(self) -> None:
        provider = _FakeToolProvider()
        engine = _make_bare_engine(provider)
        engine.conversation.add_user_message("Führ ein Tool aus.")

        response = provider.send(engine.conversation.get_messages(), "")
        engine._process_response(response, "Führ ein Tool aus.")

        stage_calls = [
            call.args[0] for call in engine.event_bus.publish.call_args_list
            if isinstance(call.args[0], ProcessingStageEvent)
        ]
        stages = [e.stage for e in stage_calls]
        self.assertEqual(stages, ["tool_exec", "tool_followup"])
        self.assertIn("fake", stage_calls[0].detail)

    def test_reasoning_stage_published_when_response_has_reasoning(self) -> None:
        provider = _FakeToolProvider()
        engine = _make_bare_engine(provider)
        engine.conversation.add_user_message("Führ ein Tool aus.")

        response = provider.send(engine.conversation.get_messages(), "")
        # Simulate a follow-up response carrying captured <think> content.
        provider.send_tool_result = lambda *a, **kw: LLMResponse(
            text="Erledigt, Sir.", tool_calls=[], reasoning="kurz überlegt",
        )
        engine._process_response(response, "Führ ein Tool aus.")

        reasoning_events = [
            call.args[0] for call in engine.event_bus.publish.call_args_list
            if isinstance(call.args[0], ProcessingStageEvent) and call.args[0].stage == "reasoning"
        ]
        self.assertEqual(len(reasoning_events), 1)
        self.assertEqual(reasoning_events[0].reasoning, "kurz überlegt")

    def test_tool_call_with_empty_text_on_both_sides_never_returns_empty(self) -> None:
        """Regression test for a live-reproduced stuck-state bug: if the
        model emits only a tool call with no text, AND the tool-followup
        response also comes back with no text (e.g. after a failed tool
        execution), _process_response must still return non-empty text -
        an empty return meant _handle_input's `if spoken:` never fired, so
        no ResponseReadyEvent/speak() ever happened and the client's
        "Denkt nach..." indicator stayed active forever even though the
        server had already finished the turn."""
        provider = _FakeToolProvider()
        engine = _make_bare_engine(provider)
        engine.conversation.add_user_message("Erzähle mir eine Geschichte.")

        response = provider.send(engine.conversation.get_messages(), "")
        # Both the tool call's own response and the followup carry no text.
        provider.send_tool_result = lambda *a, **kw: LLMResponse(text="", tool_calls=[])
        spoken = engine._process_response(response, "Erzähle mir eine Geschichte.")

        self.assertTrue(spoken)


class ErrorResponsesAreNotPersistedTests(unittest.TestCase):
    """Regression tests for a live-observed conversation-history poisoning
    bug: an API-error placeholder ("Gemini API Fehler: 400", "Mistral API
    Fehler: 400") used to be stored via add_assistant_response() as if it
    were a real answer. Once stored, it (and the broken tool_use turn next
    to it) got replayed on every future call to that provider, which then
    rejected the same malformed historical turn again - and again."""

    def test_error_response_without_tool_call_is_spoken_but_not_persisted(self) -> None:
        provider = _FakeToolProvider()
        engine = _make_bare_engine(provider)
        engine.conversation.add_user_message("Wie geht es dir?")

        error_response = LLMResponse(text="Gemini API Fehler: 400", tool_calls=[], is_error=True)
        spoken = engine._process_response(error_response, "Wie geht es dir?")

        self.assertEqual(spoken, "Gemini API Fehler: 400")
        messages = engine.conversation.get_messages()
        self.assertNotIn("Gemini API Fehler: 400", str(messages))

    def test_error_followup_after_tool_call_is_spoken_but_not_persisted(self) -> None:
        provider = _FakeToolProvider()
        engine = _make_bare_engine(provider)
        engine.conversation.add_user_message("Führ ein Tool aus.")

        response = provider.send(engine.conversation.get_messages(), "")
        provider.send_tool_result = lambda *a, **kw: LLMResponse(
            text="Mistral API Fehler: 400", tool_calls=[], is_error=True,
        )
        spoken = engine._process_response(response, "Führ ein Tool aus.")

        self.assertIn("Mistral API Fehler: 400", spoken)
        messages = engine.conversation.get_messages()
        self.assertNotIn("Mistral API Fehler: 400", str(messages))


class SpeakIfNotStaleTests(unittest.TestCase):
    """Regression tests for the orphaned-thread fix: a cancelled turn that
    also outlasts the gRPC watchdog used to still speak/broadcast its
    eventual result with nothing left to suppress it (see
    TarnoGrpcBridge._cleanup_orphaned_generation). _speak_if_not_stale is the
    single choke point _handle_input now routes every final speak() through."""

    @staticmethod
    def _make_engine() -> TarnoEngine:
        engine = object.__new__(TarnoEngine)
        engine.event_bus = MagicMock()
        engine.synthesizer = MagicMock()
        engine._current_chat_id = "default"
        engine._current_turn_id = ""
        engine.speak_responses_enabled = True
        return engine

    def test_speaks_when_not_stale(self) -> None:
        engine = self._make_engine()
        engine._speak_if_not_stale("Hallo", is_stale=lambda: False)
        engine.synthesizer.speak.assert_called_once_with("Hallo")
        engine.event_bus.publish.assert_called_once()

    def test_suppressed_when_stale(self) -> None:
        engine = self._make_engine()
        engine._speak_if_not_stale("Hallo", is_stale=lambda: True)
        engine.synthesizer.speak.assert_not_called()
        engine.event_bus.publish.assert_not_called()

    def test_none_is_stale_means_never_stale(self) -> None:
        """No is_stale callback (console/voice standalone modes, which have
        no gRPC generation concept) must never suppress speaking."""
        engine = self._make_engine()
        engine._speak_if_not_stale("Hallo", is_stale=None)
        engine.synthesizer.speak.assert_called_once_with("Hallo")


if __name__ == "__main__":
    unittest.main()
