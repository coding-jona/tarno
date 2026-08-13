"""Tests that TarnoGrpcBridge actually arms AuditManager for the gRPC/WinUI
launch path.

TarnoEngine.run()/run_text_mode() call AuditManager.save_state()/
verify_integrity()/rotate_old_logs(), but the gRPC backend drives the engine
directly via _handle_input() and never calls either method - so without
explicit wiring in the bridge, the audit-log integrity check was silently
never armed for the WinUI launch path (the one most users actually run).
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from tarno_backend.ai.tool_registry import ToolRegistry
from tarno_backend.core.config import TarnoConfig
from tarno_backend.core.events import EventBus
from tarno_backend.grpc.server import TarnoGrpcBridge


class _FakeEngineWithAudit:
    """Stand-in engine exposing the same _audit_manager attribute TarnoEngine has."""

    def __init__(self) -> None:
        self.config = TarnoConfig()
        self.event_bus = EventBus()
        self.tools = ToolRegistry()
        self._audit_manager = MagicMock()
        self._audit_manager.verify_integrity.return_value = (True, [])


class _FakeEngineWithoutAudit:
    """Stand-in matching MockTarnoEngine: no _audit_manager attribute at all."""

    def __init__(self) -> None:
        self.config = TarnoConfig()
        self.event_bus = EventBus()
        self.tools = ToolRegistry()


class AuditWiringTests(unittest.TestCase):
    def test_baseline_saved_on_bridge_construction(self) -> None:
        engine = _FakeEngineWithAudit()
        TarnoGrpcBridge(engine)
        engine._audit_manager.save_state.assert_called_once()

    def test_shutdown_verifies_and_rotates(self) -> None:
        engine = _FakeEngineWithAudit()
        bridge = TarnoGrpcBridge(engine)
        bridge.shutdown()
        engine._audit_manager.verify_integrity.assert_called_once()
        engine._audit_manager.rotate_old_logs.assert_called_once_with(retention_days=365)

    def test_missing_audit_manager_does_not_crash(self) -> None:
        # Matches the mock engine, which has no _audit_manager at all.
        engine = _FakeEngineWithoutAudit()
        bridge = TarnoGrpcBridge(engine)
        bridge.shutdown()  # must not raise


if __name__ == "__main__":
    unittest.main()
