"""Tests for TarnoGrpcBridge.handle_set_reasoning_mode (Phase C).

Follows the same shape as the existing autonomy-mode/vision-toggle handlers:
applies the change to the engine and broadcasts the resulting state to every
connected client.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from tarno.ai.tool_registry import ToolRegistry
from tarno.core.config import TarnoConfig
from tarno.core.events import EventBus
from tarno.grpc import tarno_pb2
from tarno.grpc.server import TarnoGrpcBridge


class _FakeEngine:
    def __init__(self) -> None:
        self.config = TarnoConfig()
        self.event_bus = EventBus()
        self.tools = ToolRegistry()
        self.reasoning_effort: str | None = None

    def set_reasoning_mode(self, enabled: bool, effort: str = "medium") -> None:
        self.reasoning_effort = effort if enabled else None


class HandleSetReasoningModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = _FakeEngine()
        self.bridge = TarnoGrpcBridge(self.engine)
        self.bridge._broadcast = MagicMock()

    def test_enabling_applies_effort_and_broadcasts(self) -> None:
        self.bridge.handle_set_reasoning_mode(
            tarno_pb2.SetReasoningMode(enabled=True, effort="high")
        )

        self.assertEqual(self.engine.reasoning_effort, "high")
        self.bridge._broadcast.assert_called_once()
        message = self.bridge._broadcast.call_args[0][0]
        self.assertEqual(message.reasoning_mode_update.enabled, True)
        self.assertEqual(message.reasoning_mode_update.effort, "high")

    def test_disabling_clears_effort(self) -> None:
        self.engine.reasoning_effort = "medium"
        self.bridge.handle_set_reasoning_mode(
            tarno_pb2.SetReasoningMode(enabled=False, effort="medium")
        )

        self.assertIsNone(self.engine.reasoning_effort)
        message = self.bridge._broadcast.call_args[0][0]
        self.assertEqual(message.reasoning_mode_update.enabled, False)

    def test_missing_effort_defaults_to_medium(self) -> None:
        self.bridge.handle_set_reasoning_mode(
            tarno_pb2.SetReasoningMode(enabled=True, effort="")
        )
        self.assertEqual(self.engine.reasoning_effort, "medium")

    def test_noop_for_engine_without_reasoning_support(self) -> None:
        """Mock engine has no set_reasoning_mode - must not raise, must not broadcast."""
        class _EngineWithoutReasoning:
            def __init__(self) -> None:
                self.config = TarnoConfig()
                self.event_bus = EventBus()
                self.tools = ToolRegistry()

        bridge = TarnoGrpcBridge(_EngineWithoutReasoning())
        bridge._broadcast = MagicMock()

        bridge.handle_set_reasoning_mode(tarno_pb2.SetReasoningMode(enabled=True, effort="high"))

        bridge._broadcast.assert_not_called()


class _FakeEngineWithProvider(_FakeEngine):
    def __init__(self) -> None:
        super().__init__()
        self.provider = MagicMock()
        self.provider.name = "mistral"
        self.active_model = None

    def set_provider(self, provider_name: str, model: str | None = None):
        if provider_name == "ollama":
            self.provider = MagicMock()
            self.provider.name = "ollama"
            self.active_model = model
            return True, "Provider auf 'ollama' gewechselt."
        return False, f"Provider '{provider_name}' konnte nicht aktiviert werden."


class HandleSetProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = _FakeEngineWithProvider()
        self.bridge = TarnoGrpcBridge(self.engine)
        self.bridge._broadcast = MagicMock()

    def test_success_broadcasts_new_provider(self) -> None:
        self.bridge.handle_set_provider(tarno_pb2.SetProvider(provider="ollama"))

        message = self.bridge._broadcast.call_args[0][0]
        self.assertEqual(message.provider_update.provider, "ollama")
        self.assertTrue(message.provider_update.success)

    def test_failure_broadcasts_still_active_old_provider_not_the_wish_name(self) -> None:
        self.bridge.handle_set_provider(tarno_pb2.SetProvider(provider="does_not_exist"))

        message = self.bridge._broadcast.call_args[0][0]
        # Must reflect the still-active OLD provider ("mistral"), never the
        # failed wish-name ("does_not_exist") - this is the critical case
        # the plan calls out: no incorrect active provider shown to the UI.
        self.assertEqual(message.provider_update.provider, "mistral")
        self.assertFalse(message.provider_update.success)

    def test_noop_for_engine_without_provider_support(self) -> None:
        class _EngineWithoutProviderSwitch:
            def __init__(self) -> None:
                self.config = TarnoConfig()
                self.event_bus = EventBus()
                self.tools = ToolRegistry()

        bridge = TarnoGrpcBridge(_EngineWithoutProviderSwitch())
        bridge._broadcast = MagicMock()

        bridge.handle_set_provider(tarno_pb2.SetProvider(provider="ollama"))

        bridge._broadcast.assert_not_called()


if __name__ == "__main__":
    unittest.main()
