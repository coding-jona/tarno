"""Helpers for consuming and accumulating streaming LLM responses."""

from __future__ import annotations

from collections.abc import Iterator

from tarno.ai.provider import LLMResponse, StreamingDelta, ToolCall


def accumulate_streaming_response(stream: Iterator[StreamingDelta]) -> tuple[str, list[ToolCall]]:
    """Consume a streaming iterator and return the final text and tool calls.

    This helper is used by callers that cannot render incrementally but still
    want a uniform interface.
    """
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []

    for delta in stream:
        if delta.text:
            text_parts.append(delta.text)
        if delta.tool_call is not None:
            tool_calls.append(delta.tool_call)

    return "".join(text_parts), tool_calls


def streaming_to_llm_response(stream: Iterator[StreamingDelta]) -> LLMResponse:
    """Convert a streaming iterator into a normal LLMResponse."""
    text, tool_calls = accumulate_streaming_response(stream)
    return LLMResponse(text=text, tool_calls=tool_calls)
