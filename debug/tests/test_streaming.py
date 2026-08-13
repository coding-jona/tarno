"""Tests for LLM streaming architecture and helpers."""

from __future__ import annotations

import unittest
from typing import Any

from tarno.ai.fallback_provider import FallbackProvider
from tarno.ai.provider import LLMProvider, LLMResponse, ProviderCapabilities, StreamingDelta
from tarno.ai.streaming import accumulate_streaming_response, streaming_to_llm_response


class FakeStreamingProvider(LLMProvider):
    """Provider that yields tokens and supports streaming."""

    def __init__(self, name: str, tokens: list[str]) -> None:
        self._name = name
        self._tokens = tokens

    @property
    def name(self) -> str:
        return self._name

    @property
    def supports_tools(self) -> bool:
        return True

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(streaming=True, tool_calls=True)

    def send(self, messages, system, tools=None) -> LLMResponse:
        return LLMResponse(text="".join(self._tokens), tool_calls=[])

    def send_tool_result(self, messages, system, tools=None) -> LLMResponse:
        return self.send(messages, system, tools)

    def send_stream(self, messages, system, tools=None):
        for token in self._tokens:
            yield StreamingDelta(text=token)
        yield StreamingDelta(is_finished=True)


class NonStreamingProvider(LLMProvider):
    """Provider that does not support streaming."""

    @property
    def name(self) -> str:
        return "non-streaming"

    @property
    def supports_tools(self) -> bool:
        return True

    def send(self, messages, system, tools=None) -> LLMResponse:
        return LLMResponse(text="hello world", tool_calls=[])

    def send_tool_result(self, messages, system, tools=None) -> LLMResponse:
        return self.send(messages, system, tools)


class StreamingHelpersTests(unittest.TestCase):
    """Unit tests for streaming helper functions."""

    def test_accumulate_streaming_response(self):
        deltas = [
            StreamingDelta(text="Hallo "),
            StreamingDelta(text="Welt"),
            StreamingDelta(is_finished=True),
        ]
        text, tool_calls = accumulate_streaming_response(iter(deltas))
        self.assertEqual(text, "Hallo Welt")
        self.assertEqual(tool_calls, [])

    def test_streaming_to_llm_response(self):
        deltas = [
            StreamingDelta(text="yes"),
            StreamingDelta(is_finished=True),
        ]
        response = streaming_to_llm_response(iter(deltas))
        self.assertEqual(response.text, "yes")


class FallbackStreamingTests(unittest.TestCase):
    """Tests for streaming fallback behaviour."""

    def test_fallback_uses_streaming_provider(self):
        streaming = FakeStreamingProvider("streamer", ["A", "B", "C"])
        fallback = FallbackProvider([streaming])
        result = list(fallback.send_stream([], ""))
        self.assertEqual([d.text for d in result if d.text], ["A", "B", "C"])
        self.assertTrue(result[-1].is_finished)

    def test_fallback_falls_back_to_sync_when_no_streaming(self):
        sync = NonStreamingProvider()
        fallback = FallbackProvider([sync])
        result = list(fallback.send_stream([], ""))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].text, "hello world")
        self.assertTrue(result[0].is_finished)

    def test_capabilities_aggregates_streaming(self):
        streaming = FakeStreamingProvider("streamer", [])
        sync = NonStreamingProvider()
        fallback = FallbackProvider([sync, streaming])
        self.assertTrue(fallback.capabilities.streaming)


if __name__ == "__main__":
    unittest.main()
