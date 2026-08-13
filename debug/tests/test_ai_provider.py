"""Tests for tarno/ai/provider.py's extract_reasoning() helper.

Regression tests for the "real Denkt-nach-Anzeige" fix: provider clients
used to strip and discard <think>...</think> blocks that models occasionally
emit; extract_reasoning() captures that content instead of throwing it away.
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from tarno.ai.mistral_client import _REASONING_CAPABLE_MODELS, MistralProvider
from tarno.ai.provider import extract_reasoning


class ExtractReasoningTests(unittest.TestCase):
    def test_no_think_block_returns_text_unchanged(self) -> None:
        text, reasoning = extract_reasoning("hallo welt")
        self.assertEqual(text, "hallo welt")
        self.assertIsNone(reasoning)

    def test_think_block_is_captured_and_stripped(self) -> None:
        text, reasoning = extract_reasoning("<think>foo</think>bar")
        self.assertEqual(text, "bar")
        self.assertEqual(reasoning, "foo")

    def test_whitespace_only_think_block_yields_none_reasoning(self) -> None:
        text, reasoning = extract_reasoning("<think>   </think>antwort")
        self.assertEqual(text, "antwort")
        self.assertIsNone(reasoning)

    def test_strips_surrounding_whitespace(self) -> None:
        text, reasoning = extract_reasoning("  <think> denke nach </think>  antwort  ")
        self.assertEqual(text, "antwort")
        self.assertEqual(reasoning, "denke nach")


class MistralConvertMessageImageTests(unittest.TestCase):
    """Regression test for Phase A (Chat-Bild-Upload): _convert_message used
    to silently drop image_url content blocks (only "type"=="text" was ever
    extracted), so an uploaded image would never actually reach Mistral even
    though the UI successfully sent it."""

    def test_text_and_image_blocks_both_survive(self) -> None:
        msg = {
            "role": "user",
            "content": [
                {"type": "text", "text": "Was zeigt dieses Bild?"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AAA="}},
            ],
        }
        converted = MistralProvider._convert_message(msg)

        self.assertEqual(converted["role"], "user")
        self.assertIsInstance(converted["content"], list)
        types = [block["type"] for block in converted["content"]]
        self.assertEqual(types, ["text", "image_url"])
        self.assertEqual(converted["content"][0]["text"], "Was zeigt dieses Bild?")
        self.assertEqual(
            converted["content"][1]["image_url"]["url"],
            "data:image/jpeg;base64,AAA=",
        )

    def test_image_only_block_has_no_text_part(self) -> None:
        msg = {
            "role": "user",
            "content": [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AAA="}}],
        }
        converted = MistralProvider._convert_message(msg)
        types = [block["type"] for block in converted["content"]]
        self.assertEqual(types, ["image_url"])


class MistralCapabilitiesTests(unittest.TestCase):
    def test_reasoning_effort_capability_is_true(self) -> None:
        provider = MistralProvider(api_key="fake-key-for-test")
        self.assertTrue(provider.capabilities.reasoning_effort)


class MistralReasoningEffortPayloadTests(unittest.TestCase):
    """Regression tests for Phase C (Thinking-Toggle): reasoning_effort must
    only be written into the request payload for models that actually
    support it (_REASONING_CAPABLE_MODELS), never blindly for whatever
    self._model happens to be."""

    @staticmethod
    def _send_and_capture_payload(provider: MistralProvider, reasoning_effort: str | None) -> dict:
        captured: dict = {}
        fake_response = MagicMock()
        fake_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"total_tokens": 5},
        }).encode("utf-8")
        fake_response.__enter__.return_value = fake_response

        def fake_urlopen(req, timeout=None):
            captured["payload"] = json.loads(req.data)
            return fake_response

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            provider.send(
                messages=[{"role": "user", "content": "hi"}],
                system="sys",
                reasoning_effort=reasoning_effort,
            )
        return captured["payload"]

    def test_included_for_capable_non_magistral_model(self) -> None:
        provider = MistralProvider(api_key="fake-key-for-test", model="mistral-medium-latest")
        payload = self._send_and_capture_payload(provider, "high")
        self.assertEqual(payload.get("reasoning_effort"), "high")

    def test_omitted_for_magistral_model(self) -> None:
        """Found live: Mistral's API rejects reasoning_effort outright for
        magistral models (400 "reasoning_effort is not enabled for this
        model") - they reason unconditionally and don't take the dial."""
        provider = MistralProvider(api_key="fake-key-for-test", model="magistral-small-latest")
        payload = self._send_and_capture_payload(provider, "high")
        self.assertNotIn("reasoning_effort", payload)

    def test_redirects_to_reasoning_model_for_incapable_model(self) -> None:
        """Found live: reasoning_effort used to be silently dropped when the
        selected chat model (e.g. mistral-large-latest) couldn't do it at
        all, so "Denken" never produced any visible reasoning. Redirecting
        to a reasoning-capable model keeps the toggle meaningful instead.
        The redirect target (magistral-medium-latest) reasons unconditionally,
        so reasoning_effort itself is correctly omitted after the redirect."""
        provider = MistralProvider(api_key="fake-key-for-test", model="mistral-small-latest")
        payload = self._send_and_capture_payload(provider, "high")
        self.assertIn(payload.get("model"), _REASONING_CAPABLE_MODELS)
        self.assertNotIn("reasoning_effort", payload)

    def test_omitted_when_not_requested(self) -> None:
        provider = MistralProvider(api_key="fake-key-for-test", model="magistral-small-latest")
        payload = self._send_and_capture_payload(provider, None)
        self.assertNotIn("reasoning_effort", payload)


class MistralChunkedContentParsingTests(unittest.TestCase):
    """reasoning_effort="high" makes Mistral return message.content as a
    chunk list (ThinkChunk/TextChunk) instead of a plain string."""

    def test_thinking_and_text_chunks_are_separated(self) -> None:
        result = MistralProvider._parse({
            "choices": [{"message": {"content": [
                {"type": "thinking", "thinking": [{"type": "text", "text": "Ich überlege kurz."}]},
                {"type": "text", "text": "Die Antwort lautet 42."},
            ]}}],
            "usage": {"total_tokens": 10},
        }, model="magistral-small-latest")
        self.assertEqual(result.text, "Die Antwort lautet 42.")
        self.assertEqual(result.reasoning, "Ich überlege kurz.")


class MistralToolCallIdSanitizeTests(unittest.TestCase):
    """Mistral's own API occasionally returns a tool_call.id that violates
    its OWN validation regex on the next request (live-observed: an 8-char
    id rejected with "must be a-z, A-Z, 0-9, with a length of 9"). Storing
    such an id verbatim poisons conversation history - every future call
    that replays this turn fails identically."""

    def test_valid_nine_char_id_is_kept_unchanged(self) -> None:
        result = MistralProvider._parse({
            "choices": [{"message": {
                "content": "",
                "tool_calls": [{
                    "id": "V2bduoFbR",
                    "function": {"name": "web_search", "arguments": "{}"},
                }],
            }}],
        })
        self.assertEqual(result.tool_calls[0].id, "V2bduoFbR")

    def test_non_conformant_id_is_replaced_with_valid_one(self) -> None:
        import re

        result = MistralProvider._parse({
            "choices": [{"message": {
                "content": "",
                "tool_calls": [{
                    "id": "6v41neai",  # 8 chars - fails Mistral's own regex
                    "function": {"name": "web_search", "arguments": "{}"},
                }],
            }}],
        })
        self.assertRegex(result.tool_calls[0].id, r"^[a-zA-Z0-9]{9}$")


class MistralProviderReasoningCaptureTests(unittest.TestCase):
    """Regression test: MistralProvider used to strip <think> blocks via a
    blind re.sub, discarding real reasoning content some models emit."""

    def test_think_block_in_raw_response_is_captured_not_discarded(self) -> None:
        provider = MistralProvider(api_key="fake-key-for-test")
        fake_response = MagicMock()
        fake_response.read.return_value = json.dumps({
            "choices": [{"message": {
                "content": "<think>Ich überlege kurz.</think>Die Antwort lautet 42.",
            }}],
            "usage": {"total_tokens": 10},
        }).encode("utf-8")
        fake_response.__enter__.return_value = fake_response

        with patch("urllib.request.urlopen", return_value=fake_response):
            response = provider.send(messages=[{"role": "user", "content": "test"}], system="sys")

        self.assertEqual(response.text, "Die Antwort lautet 42.")
        self.assertEqual(response.reasoning, "Ich überlege kurz.")


if __name__ == "__main__":
    unittest.main()
