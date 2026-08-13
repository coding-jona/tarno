"""Tests for GeminiProvider - the thought_signature round-trip and is_error
flags added to fix a live-observed conversation-history poisoning bug (once
a Gemini tool_use turn missing its thought_signature entered history, every
future Gemini call replaying that turn failed with the same 400 error)."""

from __future__ import annotations

import unittest

from tarno.ai.gemini_client import GeminiProvider


class GeminiToolCallThoughtSignatureTests(unittest.TestCase):
    def test_parse_captures_extra_content_on_tool_call(self) -> None:
        result = GeminiProvider._parse({
            "choices": [{"message": {
                "content": "",
                "tool_calls": [{
                    "id": "abc123",
                    "function": {"name": "calendar_today", "arguments": "{}"},
                    "extra_content": {"google": {"thought_signature": "sig-xyz"}},
                }],
            }}],
        })
        self.assertEqual(result.tool_calls[0].raw_extra, {"google": {"thought_signature": "sig-xyz"}})

    def test_convert_message_reinjects_extra_content_for_replay(self) -> None:
        block = {
            "type": "tool_use",
            "id": "abc123",
            "name": "calendar_today",
            "input": {},
            "provider_extra": {"google": {"thought_signature": "sig-xyz"}},
        }
        msg = GeminiProvider._convert_message({"role": "assistant", "content": [block]})
        self.assertEqual(
            msg["tool_calls"][0]["extra_content"],
            {"google": {"thought_signature": "sig-xyz"}},
        )

    def test_convert_message_preserves_text_alongside_tool_call(self) -> None:
        """Regression: the tool_use branch used to return early, silently
        dropping any text block collected earlier in the same content list."""
        content = [
            {"type": "text", "text": "Ich schaue kurz nach."},
            {"type": "tool_use", "id": "abc123", "name": "calendar_today", "input": {}},
        ]
        msg = GeminiProvider._convert_message({"role": "assistant", "content": content})
        self.assertEqual(msg["content"], "Ich schaue kurz nach.")


class GeminiErrorResponsesAreFlaggedTests(unittest.TestCase):
    """Every error placeholder GeminiProvider can return must set
    is_error=True, or engine._process_response would bake the error text
    into conversation history as if it were a real answer."""

    def test_parse_of_normal_response_is_not_flagged_as_error(self) -> None:
        result = GeminiProvider._parse({"choices": [{"message": {"content": "Hallo Sir."}}]})
        self.assertFalse(result.is_error)


class GeminiModelAliasTests(unittest.TestCase):
    """Regression: the model catalog used non-existent Gemini IDs like
    'gemini-3.5-flash'. GeminiProvider must canonicalize them to real API
    model IDs so pool/worker calls don't fail with a 400 error."""

    def test_canonicalizes_invalid_gemini_flash_id(self) -> None:
        provider = GeminiProvider(api_key="test-key", model="gemini-3.5-flash")
        self.assertEqual(provider._model, "gemini-2.5-flash")

    def test_canonicalizes_invalid_gemini_flash_lite_id(self) -> None:
        provider = GeminiProvider(api_key="test-key", model="gemini-3.1-flash-lite")
        self.assertEqual(provider._model, "gemini-2.5-flash-lite")

    def test_keeps_valid_gemini_model_id(self) -> None:
        provider = GeminiProvider(api_key="test-key", model="gemini-2.5-flash")
        self.assertEqual(provider._model, "gemini-2.5-flash")


if __name__ == "__main__":
    unittest.main()
