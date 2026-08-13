"""Errors during interaction handling must reach the WinUI client as a
broadcast (chat/log message), not vanish silently or crash the request
consumer task.

Regression test for: engine._handle_input()/tools.execute() raising (e.g. a
connection-refused error from a local service) used to propagate out of an
unguarded fire-and-forget asyncio.Task / bare call with no feedback to the
user - "Denkt nach..." would hang forever with nothing shown.
"""

from __future__ import annotations

import asyncio
import threading
import time
import unittest
from unittest.mock import MagicMock

from tarno_backend.core.config import TarnoConfig
from tarno_backend.core.events import EventBus, ResponseReadyEvent
from tarno_backend.grpc import tarno_pb2
from tarno_backend.grpc.server import TarnoGrpcBridge


class _FakeEngine:
    def __init__(self) -> None:
        self.config = TarnoConfig()
        self.event_bus = EventBus()
        self.tools = MagicMock()
        self._handle_input = MagicMock(side_effect=ConnectionRefusedError("boom"))


class GrpcErrorHandlingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = _FakeEngine()
        self.bridge = TarnoGrpcBridge(self.engine)
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.loop_thread.start()
        self.bridge.set_event_loop(self.loop)
        self.connection = self.bridge.add_client()

    def tearDown(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.loop_thread.join(timeout=2)
        self.loop.close()

    def _drain_broadcasts(self, timeout: float = 2.0) -> list[tarno_pb2.ServerMessage]:
        deadline = time.monotonic() + timeout
        messages: list[tarno_pb2.ServerMessage] = []
        while time.monotonic() < deadline:
            try:
                messages.append(self.connection.queue.get_nowait())
            except asyncio.QueueEmpty:
                time.sleep(0.02)
        return messages

    def test_handle_chat_input_exception_is_broadcast_not_swallowed(self) -> None:
        self.loop.call_soon_threadsafe(self.bridge.handle_chat_input, "hallo")

        messages = self._drain_broadcasts()
        error_logs = [
            m for m in messages
            if m.HasField("log") and m.log.level == "ERROR"
        ]
        error_chats = [
            m for m in messages
            if m.HasField("chat_message") and "Fehler" in m.chat_message.text
        ]
        self.assertTrue(error_logs, "expected an ERROR LogEntry broadcast")
        self.assertTrue(error_chats, "expected an assistant error chat message broadcast")

    def test_handle_command_request_exception_is_broadcast_not_raised(self) -> None:
        self.engine.tools.execute.side_effect = ConnectionRefusedError("boom")
        command = tarno_pb2.CommandRequest(name="open_app", params={})

        self.bridge.handle_command_request(command)  # must not raise

        messages = self._drain_broadcasts(timeout=1.0)
        error_logs = [
            m for m in messages
            if m.HasField("log") and m.log.level == "ERROR"
        ]
        self.assertTrue(error_logs, "expected an ERROR LogEntry broadcast")

    def test_consume_requests_survives_one_bad_message(self) -> None:
        """A raising dispatch (e.g. set_voice_active) must not kill the
        request loop - later messages from the same client must still be
        processed instead of being silently ignored forever."""
        self.bridge.set_voice_active = MagicMock(side_effect=RuntimeError("boom"))

        async def fake_requests():
            yield tarno_pb2.ClientMessage(voice_command=tarno_pb2.VoiceCommand(active=True))
            yield tarno_pb2.ClientMessage(chat_input=tarno_pb2.ChatInput(text="hallo danach"))

        from tarno_backend.grpc.server import TarnoGrpcServicer

        servicer = TarnoGrpcServicer(self.bridge)
        future = asyncio.run_coroutine_threadsafe(
            servicer._consume_requests(fake_requests(), self.connection), self.loop
        )
        future.result(timeout=2.0)  # must complete without raising

        # The second message (chat_input) must still have reached the engine
        # despite the first message's handler raising. handle_chat_input
        # dispatches to a background task, so poll briefly.
        deadline = time.monotonic() + 2.0
        while not self.engine._handle_input.called and time.monotonic() < deadline:
            time.sleep(0.02)
        self.engine._handle_input.assert_called()


class _SlowFakeEngine:
    """_handle_input blocks until released, so a test can cancel mid-flight."""

    def __init__(self) -> None:
        self.config = TarnoConfig()
        self.event_bus = EventBus()
        self.tools = MagicMock()
        self._release = threading.Event()
        self._started = threading.Event()

    def _handle_input(self, *args, **kwargs) -> None:
        text = args[0] if args else kwargs.get("text", kwargs.get("user_text", ""))
        self._started.set()
        self._release.wait(timeout=5)
        self.event_bus.publish(ResponseReadyEvent(text=f"Antwort auf: {text}"))


class CancelChatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = _SlowFakeEngine()
        self.bridge = TarnoGrpcBridge(self.engine)
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.loop_thread.start()
        self.bridge.set_event_loop(self.loop)
        self.connection = self.bridge.add_client()

    def tearDown(self) -> None:
        self.engine._release.set()
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.loop_thread.join(timeout=2)
        self.loop.close()

    def _drain_broadcasts(self, timeout: float = 2.0) -> list[tarno_pb2.ServerMessage]:
        deadline = time.monotonic() + timeout
        messages: list[tarno_pb2.ServerMessage] = []
        while time.monotonic() < deadline:
            try:
                messages.append(self.connection.queue.get_nowait())
            except asyncio.QueueEmpty:
                time.sleep(0.02)
        return messages

    def test_cancelled_response_is_not_broadcast(self) -> None:
        self.loop.call_soon_threadsafe(self.bridge.handle_chat_input, "hallo")
        self.assertTrue(self.engine._started.wait(timeout=2.0), "engine never started processing")

        self.loop.call_soon_threadsafe(self.bridge.cancel_current_chat)
        time.sleep(0.1)
        self.engine._release.set()  # let the "slow" response finish now that it's cancelled

        messages = self._drain_broadcasts(timeout=1.5)
        chat_messages = [m for m in messages if m.HasField("chat_message")]
        self.assertFalse(
            chat_messages,
            f"expected the cancelled response to be discarded, got: {chat_messages}",
        )

    def test_uncancelled_response_is_still_broadcast(self) -> None:
        """Sanity check that the cancellation gate doesn't swallow normal responses."""
        self.loop.call_soon_threadsafe(self.bridge.handle_chat_input, "hallo")
        self.assertTrue(self.engine._started.wait(timeout=2.0), "engine never started processing")
        self.engine._release.set()

        messages = self._drain_broadcasts(timeout=1.5)
        chat_messages = [m for m in messages if m.HasField("chat_message")]
        self.assertTrue(chat_messages, "expected the normal response to be broadcast")


if __name__ == "__main__":
    unittest.main()
