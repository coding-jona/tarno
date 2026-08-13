"""Tests for TarnoGrpcBridge's chat-processing watchdog: if the single
executor worker thread ever genuinely wedges (e.g. a native audio/driver
stall outside any Python-level timeout), no queued/future chat message must
be stuck behind it forever - that used to require a full app+backend
restart (user-reported "Stuck-Zustand"). The watchdog detects a turn that
exceeds a generous timeout and swaps in a fresh executor instead of waiting
forever.
"""

from __future__ import annotations

import asyncio
import time
import unittest
from unittest.mock import MagicMock

from tarno_backend.ai.tool_registry import ToolRegistry
from tarno_backend.core.config import TarnoConfig
from tarno_backend.core.events import EventBus
from tarno_backend.grpc.server import TarnoGrpcBridge


class _FakeEngine:
    def __init__(self) -> None:
        self.config = TarnoConfig()
        self.event_bus = EventBus()
        self.tools = ToolRegistry()
        self._handle_input = MagicMock()


class WatchdogTests(unittest.IsolatedAsyncioTestCase):
    async def test_wedged_turn_gets_replaced_executor_and_future_messages_still_run(self) -> None:
        engine = _FakeEngine()
        # Simulates a hung native call outstaying the watchdog timeout - long
        # enough (3s) that it CANNOT have finished naturally by the time we
        # check at 0.6s below, so a pass here can only mean the watchdog
        # actually fired, not that the wedge happened to complete on its own
        # in the background. This distinction is exactly what an earlier,
        # too-short-lived version of this test (1.0s wedge, checked at 0.6s)
        # failed to catch: a prior implementation used asyncio.wait_for()
        # around loop.run_in_executor(), which - confirmed via live testing -
        # cannot actually reclaim a worker thread once it has started running
        # a non-cooperative blocking call (fut.cancel() on an already-RUNNING
        # executor future is a no-op; wait_for then silently waits for the
        # real call to finish before it can raise TimeoutError), so it only
        # ever "worked" by accident when the wedge finished naturally around
        # the same time as the checkpoint. Finite (not e.g. time.sleep(999))
        # so the leaked worker thread doesn't block the test process's own
        # shutdown: CPython's ThreadPoolExecutor registers an atexit hook
        # that joins every worker thread it ever created, wedged or not.
        engine._handle_input = MagicMock(side_effect=lambda *args, **kwargs: time.sleep(3.0))

        bridge = TarnoGrpcBridge(engine)
        bridge._loop = asyncio.get_running_loop()
        bridge._broadcast = MagicMock()
        bridge._TURN_WATCHDOG_TIMEOUT_SECONDS = 0.2

        wedged_executor = bridge._executor
        bridge.handle_chat_input("erste Nachricht")

        # Give the watchdog time to fire (timeout 0.2s + a little slack) -
        # well before the 3s wedge could ever finish naturally.
        await asyncio.sleep(0.6)

        self.assertIsNot(bridge._executor, wedged_executor)

        # A brand new message must actually complete now, not queue forever
        # behind the wedged thread.
        engine._handle_input = MagicMock(return_value=None)
        bridge.handle_chat_input("zweite Nachricht")
        await asyncio.sleep(0.2)

        engine._handle_input.assert_called_once_with(
            "zweite Nachricht",
            None,
            "default",
            unittest.mock.ANY,
            unittest.mock.ANY,
            None,
            "chat",
        )

    async def test_is_stale_reflects_cancellation_through_watchdog_and_orphan_cleanup(self) -> None:
        """Regression test: a cancelled turn that then also outlasts the
        watchdog used to have its generation marker released (finally-block
        discard) the instant the watchdog gave up waiting - even though the
        real call kept running in the orphaned old-executor thread. Any
        output that call eventually produced had nothing left to suppress
        it. is_stale() (passed into engine._handle_input) must keep
        reporting True for the whole remaining lifetime of the orphaned
        call, and only flip back to False once it has genuinely finished."""
        engine = _FakeEngine()
        captured: dict = {}

        def wedge(*args, **kwargs):
            # is_stale is passed as the 5th positional argument (index 4).
            captured["is_stale"] = args[4] if len(args) > 4 else kwargs.get("is_stale")
            time.sleep(0.5)  # outlasts the 0.15s watchdog below

        engine._handle_input = MagicMock(side_effect=wedge)

        bridge = TarnoGrpcBridge(engine)
        bridge._loop = asyncio.get_running_loop()
        bridge._broadcast = MagicMock()
        bridge._TURN_WATCHDOG_TIMEOUT_SECONDS = 0.15

        bridge.handle_chat_input("wird gleich abgebrochen")
        await asyncio.sleep(0.05)
        bridge.cancel_current_chat()

        # Watchdog fires at ~0.15s; give it slack.
        await asyncio.sleep(0.25)
        self.assertIn("is_stale", captured)
        self.assertTrue(
            captured["is_stale"](),
            "orphaned generation must still read as stale right after the watchdog gives up",
        )

        # Let the 0.5s wedge actually finish and _cleanup_orphaned_generation run.
        await asyncio.sleep(0.4)
        self.assertFalse(
            captured["is_stale"](),
            "once the orphaned call has genuinely finished, its generation marker must be released",
        )

    async def test_normal_turn_never_triggers_executor_replacement(self) -> None:
        engine = _FakeEngine()
        engine._handle_input = MagicMock(return_value=None)

        bridge = TarnoGrpcBridge(engine)
        bridge._loop = asyncio.get_running_loop()
        bridge._broadcast = MagicMock()

        original_executor = bridge._executor
        bridge.handle_chat_input("Hallo")
        await asyncio.sleep(0.2)

        self.assertIs(bridge._executor, original_executor)


if __name__ == "__main__":
    unittest.main()
