"""Tests for the gRPC bridge's cross-process permission confirmation round-trip.

The real (non-mock) backend runs headless behind gRPC - no Qt event loop, no
attached console - so PermissionService's default Qt/console confirmation
chain would hang forever on a MEDIUM/HIGH-risk command. TarnoGrpcBridge
replaces it with a request/response round-trip over the existing gRPC
stream instead; these tests cover that round-trip directly, without needing
a real network connection or WinUI client.
"""

from __future__ import annotations

import asyncio
import threading
import time
import unittest

from tarno.ai.tool_registry import ToolRegistry
from tarno.core.command_engine import RiskLevel
from tarno.core.config import TarnoConfig
from tarno.core.events import EventBus
from tarno.core.permission_service import PermissionType
from tarno.grpc import tarno_pb2
from tarno.grpc.server import TarnoGrpcBridge


class _FakeEngine:
    """Minimal stand-in with just the attributes TarnoGrpcBridge touches."""

    def __init__(self) -> None:
        self.config = TarnoConfig()
        self.event_bus = EventBus()
        self.tools = ToolRegistry()


class PermissionRoundTripTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = _FakeEngine()
        self.bridge = TarnoGrpcBridge(self.engine)
        self.bridge._PERMISSION_TIMEOUT_SECONDS = 0.3
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.loop_thread.start()
        self.bridge.set_event_loop(self.loop)

    def tearDown(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.loop_thread.join(timeout=2)
        self.loop.close()

    def _wait_for_pending_request(self, timeout: float = 2.0) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.bridge._pending_permissions:
                return next(iter(self.bridge._pending_permissions))
            time.sleep(0.02)
        self.fail("request_permission_sync did not register a pending request in time")

    def test_response_resolves_pending_request(self) -> None:
        """A PermissionResponse with a matching request_id unblocks the caller."""
        result: dict[str, tuple[bool, bool]] = {}

        def worker() -> None:
            result["value"] = self.bridge.request_permission_sync(
                PermissionType.COMMAND_HIGH, "rm -rf /", RiskLevel.HIGH, None
            )

        t = threading.Thread(target=worker)
        t.start()
        request_id = self._wait_for_pending_request()

        self.bridge.handle_permission_response(
            tarno_pb2.PermissionResponse(request_id=request_id, approved=True, persistent=False)
        )
        t.join(timeout=2)

        self.assertFalse(t.is_alive(), "worker thread did not unblock")
        self.assertEqual(result.get("value"), (True, False))
        self.assertNotIn(request_id, self.bridge._pending_permissions, "pending entry must be cleaned up")

    def test_denied_response_is_propagated(self) -> None:
        result: dict[str, tuple[bool, bool]] = {}

        def worker() -> None:
            result["value"] = self.bridge.request_permission_sync(
                PermissionType.COMMAND_MEDIUM, "del file.txt", RiskLevel.MEDIUM, None
            )

        t = threading.Thread(target=worker)
        t.start()
        request_id = self._wait_for_pending_request()

        self.bridge.handle_permission_response(
            tarno_pb2.PermissionResponse(request_id=request_id, approved=False, persistent=False)
        )
        t.join(timeout=2)

        self.assertEqual(result.get("value"), (False, False))

    def test_times_out_and_denies_when_no_response_arrives(self) -> None:
        approved, persistent = self.bridge.request_permission_sync(
            PermissionType.COMMAND_MEDIUM, "del file.txt", RiskLevel.MEDIUM, None
        )
        self.assertEqual((approved, persistent), (False, False))
        self.assertEqual(self.bridge._pending_permissions, {}, "timed-out entry must be cleaned up")

    def test_response_for_unknown_request_id_is_ignored_not_raised(self) -> None:
        # Must not raise even though nothing is pending for this id.
        self.bridge.handle_permission_response(
            tarno_pb2.PermissionResponse(request_id="does-not-exist", approved=True, persistent=False)
        )

    def test_high_risk_request_carries_safety_phrase(self) -> None:
        received: dict[str, tarno_pb2.ServerMessage] = {}
        original_broadcast = self.bridge._broadcast

        def spy_broadcast(message: tarno_pb2.ServerMessage) -> None:
            if message.HasField("permission_request"):
                received["message"] = message
            original_broadcast(message)

        self.bridge._broadcast = spy_broadcast  # type: ignore[assignment]

        def worker() -> None:
            self.bridge.request_permission_sync(
                PermissionType.COMMAND_HIGH, "format C:", RiskLevel.HIGH, None
            )

        t = threading.Thread(target=worker)
        t.start()
        request_id = self._wait_for_pending_request()
        self.bridge.handle_permission_response(
            tarno_pb2.PermissionResponse(request_id=request_id, approved=False, persistent=False)
        )
        t.join(timeout=2)

        self.assertIn("message", received)
        self.assertTrue(received["message"].permission_request.safety_phrase)


if __name__ == "__main__":
    unittest.main()
