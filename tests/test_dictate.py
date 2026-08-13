"""Tests for TarnoGrpcBridge.dictate_once (Phase B: In-Chat-Diktat).

_blocking_dictate itself touches real hardware (PyAudio microphone,
faster-whisper model) and is not exercised here - these tests cover the
dispatch logic: the mic-conflict guard must refuse immediately without ever
constructing a recognizer/audio stream, and a normal call must delegate to
_blocking_dictate via the executor and propagate its result.
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from tarno.ai.tool_registry import ToolRegistry
from tarno.core.config import TarnoConfig
from tarno.core.events import EventBus
from tarno.grpc.server import TarnoGrpcBridge


class _FakeEngine:
    def __init__(self) -> None:
        self.config = TarnoConfig()
        self.event_bus = EventBus()
        self.tools = ToolRegistry()


class DictateOnceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.engine = _FakeEngine()
        self.bridge = TarnoGrpcBridge(self.engine)

    async def test_refuses_immediately_when_voice_mode_active(self) -> None:
        self.bridge._voice_controller = MagicMock(active=True)
        self.bridge._blocking_dictate = MagicMock()

        success, text, error = await self.bridge.dictate_once("medium")

        self.assertFalse(success)
        self.assertEqual(text, "")
        self.assertIn("Sprachmodus belegt", error)
        self.bridge._blocking_dictate.assert_not_called()

    async def test_proceeds_when_voice_controller_is_none(self) -> None:
        self.bridge._voice_controller = None
        self.bridge._blocking_dictate = MagicMock(return_value=(True, "Hallo Welt", ""))

        success, text, error = await self.bridge.dictate_once("high")

        self.assertTrue(success)
        self.assertEqual(text, "Hallo Welt")
        self.assertEqual(error, "")
        self.bridge._blocking_dictate.assert_called_once_with("high")

    async def test_proceeds_when_voice_controller_inactive(self) -> None:
        self.bridge._voice_controller = MagicMock(active=False)
        self.bridge._blocking_dictate = MagicMock(return_value=(False, "", "Keine Sprache erkannt."))

        success, text, error = await self.bridge.dictate_once("low")

        self.assertFalse(success)
        self.assertEqual(error, "Keine Sprache erkannt.")
        self.bridge._blocking_dictate.assert_called_once_with("low")


if __name__ == "__main__":
    unittest.main()
