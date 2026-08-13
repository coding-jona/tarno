"""Tests that TarnoGrpcBridge actually starts/stops ExtensionCoordinator and
ProactiveEngine for the gRPC/WinUI launch path.

Found via live testing: TarnoEngine.run()/run_text_mode() (voice/console
launch modes) already call ._extensions.start() and ._proactive_engine.start(),
but the gRPC backend drives the engine directly via _handle_input() and never
called either - so a reminder added via add_reminder was stored correctly in
reminders.json but never actually checked/spoken, and the vision observer's
camera would open on toggle but never get ticked for motion detection. Same
bug class as _save_audit_baseline() (see test_grpc_audit_wiring.py).
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from tarno.ai.tool_registry import ToolRegistry
from tarno.core.config import TarnoConfig
from tarno.core.events import EventBus
from tarno.grpc.server import TarnoGrpcBridge


class _FakeEngineWithBackgroundLoops:
    """Stand-in engine exposing the same attributes TarnoEngine has."""

    def __init__(self) -> None:
        self.config = TarnoConfig()
        self.event_bus = EventBus()
        self.tools = ToolRegistry()
        self._extensions = MagicMock()
        self._proactive_engine = MagicMock()
        self._vision_observer = MagicMock()


class _FakeEngineWithoutBackgroundLoops:
    """Stand-in matching MockTarnoEngine: none of these attributes exist."""

    def __init__(self) -> None:
        self.config = TarnoConfig()
        self.event_bus = EventBus()
        self.tools = ToolRegistry()


class BackgroundLoopsWiringTests(unittest.TestCase):
    def test_extensions_and_proactive_engine_started_on_construction(self) -> None:
        engine = _FakeEngineWithBackgroundLoops()
        TarnoGrpcBridge(engine)
        engine._extensions.start.assert_called_once()
        engine._proactive_engine.start.assert_called_once()

    def test_shutdown_stops_extensions_proactive_engine_and_closes_vision(self) -> None:
        engine = _FakeEngineWithBackgroundLoops()
        bridge = TarnoGrpcBridge(engine)
        bridge.shutdown()
        engine._extensions.stop.assert_called_once()
        engine._proactive_engine.stop.assert_called_once()
        engine._vision_observer.close.assert_called_once()

    def test_missing_background_loop_attributes_does_not_crash(self) -> None:
        # Matches the mock engine, which has none of these attributes.
        engine = _FakeEngineWithoutBackgroundLoops()
        bridge = TarnoGrpcBridge(engine)
        bridge.shutdown()  # must not raise


if __name__ == "__main__":
    unittest.main()
