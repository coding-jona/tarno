"""Unit tests for TARNO core modules."""

from __future__ import annotations

import datetime
import json
import os
import tempfile
import unittest
import uuid
from collections import deque
from pathlib import Path
from unittest.mock import patch

from ovos_bus_client.message import Message

from tarno.ai.conversation import ConversationManager
from tarno.ai.fallback_provider import FallbackProvider
from tarno.ai.mistral_client import MistralProvider
from tarno.ai.provider import LLMProvider, LLMResponse, ToolCall
from tarno.ai.response_guard import guard_response
from tarno.ai.tool_registry import ToolDefinition, ToolRegistry
from tarno.core.calendar_service import CalendarService
from tarno.core.config import AudioConfig, TarnoConfig, MemoryConfig
from tarno.core.agent_service import AgentService
from tarno.desktop.file_manager import list_directory, read_file, write_file
from tarno.utils.text import is_exit


class _FakeBus:
    """Minimal fake MessageBusClient that records emitted messages."""

    def __init__(self) -> None:
        self.emitted: list[Message] = []
        self._handlers: dict[str, list[callable]] = {}

    def on(self, event: str, handler: callable) -> None:
        self._handlers.setdefault(event, []).append(handler)

    def remove(self, event: str, handler: callable) -> None:
        self._handlers.get(event, []).remove(handler)

    def emit(self, message: Message) -> None:
        self.emitted.append(message)


class _FakeProvider(LLMProvider):
    """Fake LLM provider for agent tests."""

    def __init__(self, response: str = "Hallo, Sir.") -> None:
        self._response = response

    @property
    def name(self) -> str:
        return "fake"

    @property
    def supports_tools(self) -> bool:
        return True

    def send(self, messages, system, tools=None):
        return LLMResponse(text=self._response, tool_calls=[])

    def send_tool_result(self, messages, system, tools=None):
        return self.send(messages, system, tools)


class _FakeToolProvider(LLMProvider):
    """Fake provider that requests one tool call, then returns a final text response."""

    def __init__(self) -> None:
        self._call = 0

    @property
    def name(self) -> str:
        return "fake_tool"

    @property
    def supports_tools(self) -> bool:
        return True

    def send(self, messages, system, tools=None):
        self._call += 1
        if self._call == 1:
            return LLMResponse(
                text="",
                tool_calls=[ToolCall(id="call_1", name="fake", input={})],
            )
        return LLMResponse(text="Erledigt, Sir.", tool_calls=[])

    def send_tool_result(self, messages, system, tools=None):
        return self.send(messages, system, tools)


class _FailingProvider(LLMProvider):
    """Fake LLM provider that always raises."""

    def __init__(self, message: str = "fail") -> None:
        self._message = message

    @property
    def name(self) -> str:
        return "failing"

    @property
    def supports_tools(self) -> bool:
        return True

    def send(self, messages, system, tools=None):
        raise RuntimeError(self._message)

    def send_tool_result(self, messages, system, tools=None):
        raise RuntimeError(self._message)


class _NoToolProvider(_FakeProvider):
    """Fake LLM provider that does not support tools."""

    @property
    def supports_tools(self) -> bool:
        return False


class ConversationManagerTests(unittest.TestCase):
    """Tests for ConversationManager persistence and message handling."""

    def test_add_and_get_messages(self):
        cm = ConversationManager(max_history=10)
        cm.add_user_message("Hallo")
        cm.add_assistant_response("Hallo, Sir.")
        messages = cm.get_messages()
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[1]["role"], "assistant")

    def test_memory_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            memory = MemoryConfig(enabled=True, storage_dir=d, conversation_id="test")
            cm = ConversationManager(max_history=10, memory=memory)
            cm.add_user_message("Hallo")
            cm.add_assistant_response("Hallo, Sir.")

            cm2 = ConversationManager(max_history=10, memory=memory)
            self.assertEqual(len(cm2.get_messages()), 2)

    def test_add_user_message_with_image_builds_content_blocks(self):
        """Phase A (Chat-Bild-Upload): with an image_data_url, the stored
        content must become a [text, image_url] block list (not a plain
        string), matching the format add_assistant_response already uses."""
        cm = ConversationManager(max_history=10)
        cm.add_user_message("Was zeigt das?", image_data_url="data:image/jpeg;base64,AAA=")
        messages = cm.get_messages()
        self.assertEqual(len(messages), 1)
        content = messages[0]["content"]
        self.assertIsInstance(content, list)
        self.assertEqual(content[0], {"type": "text", "text": "Was zeigt das?"})
        self.assertEqual(content[1]["image_url"]["url"], "data:image/jpeg;base64,AAA=")

    def test_add_user_message_without_image_stays_plain_string(self):
        cm = ConversationManager(max_history=10)
        cm.add_user_message("Hallo")
        self.assertEqual(cm.get_messages()[0]["content"], "Hallo")

    def test_max_history(self):
        cm = ConversationManager(max_history=3)
        for i in range(5):
            cm.add_user_message(str(i))
        self.assertEqual(len(cm.get_messages()), 3)

    def test_sanitize_corrupted_tool_order(self):
        """Tool results placed before the assistant tool_use must be moved after it."""
        cm = ConversationManager(max_history=20)
        cm._history.append({"role": "user", "content": "Führ ein Tool aus."})
        cm._history.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": "call_1", "content": "Ergebnis"}]})
        cm._history.append({"role": "assistant", "content": [{"type": "tool_use", "id": "call_1", "name": "fake", "input": {}}]})
        messages = cm.get_messages()
        roles = [m["role"] for m in messages]
        self.assertEqual(roles, ["user", "assistant", "user"])

    def test_sanitize_removes_orphan_tool_results(self):
        """Tool results without a matching assistant tool_use are removed."""
        cm = ConversationManager(max_history=20)
        cm._history.append({"role": "user", "content": "Hallo"})
        cm._history.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": "orphan", "content": "x"}]})
        messages = cm.get_messages()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "user")

    def test_non_serializable_values_roundtrip(self):
        """Regression test: datetime, Path, set and UUID must not break persistence."""
        with tempfile.TemporaryDirectory() as d:
            memory = MemoryConfig(
                enabled=True, storage_dir=d, conversation_id="roundtrip"
            )
            cm = ConversationManager(max_history=10, memory=memory)
            cm._history.append(
                {
                    "role": "user",
                    "content": "test",
                    "meta": {
                        "created": datetime.datetime.now(),
                        "path": Path(d),
                        "tags": {"a", "b"},
                        "id": uuid.uuid4(),
                    },
                }
            )
            cm._save()
            cm2 = ConversationManager(max_history=10, memory=memory)
            messages = cm2.get_messages()
            self.assertEqual(len(messages), 1)
            meta = messages[0].get("meta", {})
            self.assertIsInstance(meta["created"], str)
            self.assertIsInstance(meta["path"], str)
            self.assertIsInstance(meta["tags"], list)
            self.assertIsInstance(meta["id"], str)


class ConfigRecoveryTests(unittest.TestCase):
    """Regression tests for OVOS config recovery."""

    def test_corrupted_mycroft_conf_is_restored(self):
        import sys

        saved = {
            k: os.environ.get(k)
            for k in (
                "TARNO_HOME",
                "XDG_CONFIG_HOME",
                "XDG_CACHE_HOME",
                "XDG_DATA_HOME",
            )
        }
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["TARNO_HOME"] = tmp
            # Import must happen after TARNO_HOME is set so the module-level
            # runtime paths point to the temporary directory.
            if "tarno.core.ovos_engine" in sys.modules:
                del sys.modules["tarno.core.ovos_engine"]
            from tarno.core.ovos_engine import _seed_user_config

            _seed_user_config()
            mycroft_conf = Path(tmp) / "config" / "mycroft" / "mycroft.conf"
            self.assertTrue(mycroft_conf.exists())
            data = json.loads(mycroft_conf.read_text(encoding="utf-8"))
            self.assertIn("websocket", data)
            self.assertEqual(data["websocket"]["host"], "127.0.0.1")

            # Corrupt the config and reseed; it should be restored from bundle.
            mycroft_conf.write_text("CORRUPT JSON", encoding="utf-8")
            _seed_user_config()
            data = json.loads(mycroft_conf.read_text(encoding="utf-8"))
            self.assertIn("websocket", data)
            self.assertEqual(data["websocket"]["host"], "127.0.0.1")
            backup = mycroft_conf.with_suffix(".conf.backup")
            self.assertTrue(backup.exists())

        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if "tarno.core.ovos_engine" in sys.modules:
            del sys.modules["tarno.core.ovos_engine"]


class ToolRegistryTests(unittest.TestCase):
    """Tests for ToolRegistry."""

    def test_register_and_execute(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="greet",
            description="Greets someone",
            input_schema={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
            handler=lambda name: f"Hallo {name}",
        ))
        schemas = registry.get_tool_schemas()
        self.assertEqual(len(schemas), 1)
        self.assertEqual(schemas[0]["name"], "greet")
        result = registry.execute("greet", {"name": "TARNO"})
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Hallo TARNO")

    def test_execute_unknown_tool(self):
        registry = ToolRegistry()
        result = registry.execute("missing", {})
        self.assertFalse(result.success)
        self.assertIn("Unbekanntes Tool", result.message)

    def test_execute_tool_error(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="fail",
            description="Always fails",
            input_schema={"type": "object", "properties": {}},
            handler=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        ))
        result = registry.execute("fail", {})
        self.assertFalse(result.success)
        self.assertIn("Fehler", result.message)


class CalendarServiceTests(unittest.TestCase):
    """Tests for iCalendar parsing."""

    def test_parse_event(self):
        from datetime import datetime, timedelta
        future = datetime.now() + timedelta(days=1)
        dt_start = future.strftime("%Y%m%dT%H%M%SZ")
        dt_end = (future + timedelta(hours=1)).strftime("%Y%m%dT%H%M%SZ")
        date_str = future.strftime("%d.%m.%Y")
        with tempfile.NamedTemporaryFile("w", suffix=".ics", delete=False, encoding="utf-8") as f:
            f.write(
                "BEGIN:VCALENDAR\n"
                "VERSION:2.0\n"
                "BEGIN:VEVENT\n"
                f"DTSTART:{dt_start}\n"
                f"DTEND:{dt_end}\n"
                "SUMMARY:Test-Termin\n"
                "END:VEVENT\n"
                "END:VCALENDAR\n"
            )
            path = f.name
        try:
            service = CalendarService(path)
            events = service.get_events(days_ahead=2)
            self.assertIn("Test-Termin", events)
            self.assertIn(date_str, events)
        finally:
            os.unlink(path)

    def test_no_calendar_configured(self):
        service = CalendarService(None)
        self.assertEqual(service.get_events(), "Kein Kalender konfiguriert.")

    def test_missing_file(self):
        service = CalendarService("/nonexistent/calendar.ics")
        self.assertIn("nicht gefunden", service.get_events())


class TarnoConfigTests(unittest.TestCase):
    """Tests for configuration loading."""

    def test_default_config(self):
        config = TarnoConfig()
        self.assertEqual(config.language, "de")
        self.assertEqual(config.audio.voice, "Trelis/piper-de-de-thorsten-medium")
        self.assertTrue(config.memory.enabled)

    def test_audio_defaults_for_latency(self):
        config = AudioConfig()
        self.assertEqual(config.speed, 1.1)
        self.assertEqual(config.whisper_beam_size, 2)
        self.assertEqual(config.pause_threshold, 3.0)


class AgentServiceTests(unittest.TestCase):
    """Tests for AgentService handling of utterances."""

    def setUp(self):
        self._orig_key = os.environ.get("MISTRAL_API_KEY")
        os.environ["MISTRAL_API_KEY"] = "dummy"

    def tearDown(self):
        if self._orig_key is None:
            os.environ.pop("MISTRAL_API_KEY", None)
        else:
            os.environ["MISTRAL_API_KEY"] = self._orig_key

    def test_handle_utterance(self):
        bus = _FakeBus()
        config = TarnoConfig()
        agent = AgentService(bus, config)
        agent._provider = _FakeProvider("Hallo, Sir. Ich bin bereit.")

        message = Message("recognizer_loop:utterance", data={"utterances": ["Hallo TARNO"], "lang": "de"})
        agent._handle_utterance(message)

        speak_messages = [m for m in bus.emitted if m.msg_type == "speak"]
        self.assertEqual(len(speak_messages), 1)
        self.assertEqual(speak_messages[0].msg_type, "speak")
        self.assertEqual(speak_messages[0].data["utterance"], "Hallo, Sir. Ich bin bereit.")

    def test_process_response_tool_order(self):
        """Tool result messages must be recorded after the assistant tool_use message."""
        bus = _FakeBus()
        config = TarnoConfig()
        config.memory.enabled = False
        agent = AgentService(bus, config)
        agent._provider = _FakeToolProvider()
        agent._tools = ToolRegistry()
        agent._tools.register(ToolDefinition(
            name="fake",
            description="Fake tool",
            input_schema={"type": "object", "properties": {}},
            handler=lambda: "Fake-Ergebnis",
        ))

        agent._conversation.add_user_message("Führ ein Tool aus.")
        response = agent._provider.send(agent._conversation.get_messages(), "")
        spoken = agent._process_response(response)

        self.assertEqual(spoken, "Erledigt, Sir.")
        messages = agent._conversation.get_messages()
        roles = [m["role"] for m in messages]
        # Expected: user, assistant(tool_use), user(tool_result), assistant
        self.assertEqual(roles, ["user", "assistant", "user", "assistant"])


class MistralProviderTests(unittest.TestCase):
    """Tests for Mistral message conversion."""

    def setUp(self):
        self._orig_key = os.environ.get("MISTRAL_API_KEY")
        os.environ["MISTRAL_API_KEY"] = "dummy"

    def tearDown(self):
        if self._orig_key is None:
            os.environ.pop("MISTRAL_API_KEY", None)
        else:
            os.environ["MISTRAL_API_KEY"] = self._orig_key

    def test_convert_multiple_tool_use_blocks(self):
        """A single assistant message with multiple tool_use blocks must produce all tool_calls.

        "call_1"/"call_2" aren't valid Mistral ids (must be 9 alphanumeric
        chars) so _convert_message sanitizes them on the send path - assert
        the sanitized ids are well-formed and distinct, not the raw input."""
        provider = MistralProvider()
        msg = {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Ich prüfe das."},
                {"type": "tool_use", "id": "call_1", "name": "get_system_info", "input": {}},
                {"type": "tool_use", "id": "call_2", "name": "get_calendar_events", "input": {}},
            ],
        }
        converted = provider._convert_message(msg)
        self.assertEqual(converted["role"], "assistant")
        self.assertEqual(converted["content"], "Ich prüfe das.")
        self.assertEqual(len(converted["tool_calls"]), 2)
        self.assertRegex(converted["tool_calls"][0]["id"], r"^[a-zA-Z0-9]{9}$")
        self.assertRegex(converted["tool_calls"][1]["id"], r"^[a-zA-Z0-9]{9}$")
        self.assertNotEqual(converted["tool_calls"][0]["id"], converted["tool_calls"][1]["id"])

    def test_convert_tool_result_non_string_content(self):
        """Tool result content that is not a string must be JSON encoded."""
        provider = MistralProvider()
        msg = {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "call_1", "content": {"status": "ok"}},
            ],
        }
        converted = provider._convert_message(msg)
        self.assertEqual(converted["role"], "tool")
        self.assertRegex(converted["tool_call_id"], r"^[a-zA-Z0-9]{9}$")
        self.assertEqual(converted["content"], '{"status": "ok"}')

    def test_foreign_provider_tool_call_id_sanitized_consistently(self):
        """Regression test for the cross-provider API-error cascade (see
        plan): a tool_use id minted by a DIFFERENT provider (e.g. an 8-char
        Groq-style id, invalid for Mistral's 9-char regex) must sanitize to
        the SAME output whether encountered via the tool_use block or its
        paired tool_result block - otherwise the pairing itself breaks even
        after sanitization."""
        provider = MistralProvider()
        foreign_id = "yiolww12"  # 8 chars - invalid for Mistral, real id observed live
        tool_use_msg = {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": foreign_id, "name": "list_directory", "input": {}}],
        }
        tool_result_msg = {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": foreign_id, "content": "ok"}],
        }
        converted_use = provider._convert_message(tool_use_msg)
        converted_result = provider._convert_message(tool_result_msg)
        self.assertRegex(converted_use["tool_calls"][0]["id"], r"^[a-zA-Z0-9]{9}$")
        self.assertEqual(converted_use["tool_calls"][0]["id"], converted_result["tool_call_id"])

    def test_convert_empty_assistant_string_content_gets_placeholder(self):
        """Mistral rejects assistant messages with empty content and no
        tool_calls - a stored empty turn must not brick the whole history."""
        provider = MistralProvider()
        converted = provider._convert_message({"role": "assistant", "content": ""})
        self.assertEqual(converted["content"], "...")

    def test_convert_empty_assistant_text_block_gets_placeholder(self):
        provider = MistralProvider()
        converted = provider._convert_message({
            "role": "assistant",
            "content": [{"type": "text", "text": ""}],
        })
        self.assertEqual(converted["content"], "...")


class MistralDifficultyTests(unittest.TestCase):
    """Tests for the per-request difficulty-tier model selection."""

    def setUp(self):
        self._orig_key = os.environ.get("MISTRAL_API_KEY")
        os.environ["MISTRAL_API_KEY"] = "dummy"

    def tearDown(self):
        if self._orig_key is None:
            os.environ.pop("MISTRAL_API_KEY", None)
        else:
            os.environ["MISTRAL_API_KEY"] = self._orig_key

    def test_short_message_is_low_difficulty(self):
        self.assertEqual(MistralProvider._classify_difficulty("Hallo"), "low")

    def test_long_message_is_medium_difficulty(self):
        # Regression: "high" is no longer reachable from the classifier at
        # all (word count included) - only via the explicit manual
        # "Starkes Modell"-toggle. A long message just stays "medium".
        text = " ".join(["Wort"] * 50)
        self.assertEqual(MistralProvider._classify_difficulty(text), "medium")

    def test_medium_length_message_is_medium_difficulty(self):
        text = " ".join(["Wort"] * 20)
        self.assertEqual(MistralProvider._classify_difficulty(text), "medium")

    def test_tool_adjacent_word_no_longer_forces_high(self):
        """Regression test for the "Datei"-Bug: a message containing a
        tool-adjacent word (e.g. "Datei") used to be force-classified as
        "high" via a keyword regex, routing an ordinary chat request to a
        slow specialized model. That keyword path is now removed entirely -
        classification is pure word-count."""
        self.assertEqual(
            MistralProvider._classify_difficulty("schreibe eine Datei über Vögel"), "low"
        )

    def test_last_user_text_extracts_plain_string(self):
        messages = [
            {"role": "user", "content": "erste Frage"},
            {"role": "assistant", "content": "Antwort"},
            {"role": "user", "content": "zweite Frage"},
        ]
        self.assertEqual(MistralProvider._last_user_text(messages), "zweite Frage")

    def test_last_user_text_extracts_from_content_blocks(self):
        messages = [
            {"role": "user", "content": [{"type": "text", "text": "Blocktext"}]},
        ]
        self.assertEqual(MistralProvider._last_user_text(messages), "Blocktext")

    def test_difficulty_disabled_keeps_configured_model(self):
        provider = MistralProvider(
            model="mistral-small-latest",
            difficulty_tiers={"low": "ministral-3b-2512", "medium": "mistral-small-2506", "high": "mistral-small-2506"},
            difficulty_enabled=False,
        )
        captured = {}

        def fake_call(payload, allow_fallback=True):
            captured["model"] = payload["model"]
            return LLMResponse(text="ok", tool_calls=[])

        provider._call = fake_call
        provider.send(messages=[{"role": "user", "content": "Hallo"}], system="sys")
        self.assertEqual(captured["model"], "mistral-small-latest")

    def test_difficulty_enabled_but_thinking_off_keeps_configured_model(self):
        """Regression: tier routing must only apply while Thinking (reasoning_effort)
        is active - with Thinking off, difficulty_enabled alone must NOT
        switch the model, even for a short message that would otherwise
        classify as "low"."""
        provider = MistralProvider(
            model="mistral-small-latest",
            difficulty_tiers={"low": "ministral-3b-2512", "medium": "mistral-small-2506", "high": "mistral-medium-2508"},
            difficulty_enabled=True,
        )
        captured = {}

        def fake_call(payload, allow_fallback=True):
            captured["model"] = payload["model"]
            return LLMResponse(text="ok", tool_calls=[])

        provider._call = fake_call
        provider.send(messages=[{"role": "user", "content": "Hallo"}], system="sys")
        self.assertEqual(captured["model"], "mistral-small-latest")

    def test_difficulty_enabled_and_thinking_on_picks_low_tier_for_short_message(self):
        provider = MistralProvider(
            model="mistral-small-latest",
            difficulty_tiers={"low": "ministral-3b-2512", "medium": "mistral-small-2506", "high": "mistral-medium-2508"},
            difficulty_enabled=True,
        )
        captured = {}

        def fake_call(payload, allow_fallback=True):
            captured["model"] = payload["model"]
            return LLMResponse(text="ok", tool_calls=[])

        provider._call = fake_call
        provider.send(
            messages=[{"role": "user", "content": "Hallo"}], system="sys",
            reasoning_effort="medium",
        )
        # Low tier is selected for short messages, but because "Hallo" enables
        # reasoning and ministral-3b cannot do reasoning_effort, the provider
        # redirects to the default reasoning-capable model.
        self.assertEqual(captured["model"], "magistral-medium-latest")

    def test_use_high_tier_bypasses_classification(self):
        provider = MistralProvider(
            model="mistral-small-latest",
            difficulty_tiers={"low": "ministral-3b-2512", "medium": "mistral-small-2506", "high": "mistral-medium-2508"},
            difficulty_enabled=True,
        )
        captured = {}

        def fake_call(payload, allow_fallback=True):
            captured["model"] = payload["model"]
            return LLMResponse(text="ok", tool_calls=[])

        provider._call = fake_call
        # Short message would normally classify as "low" - use_high_tier must override that.
        provider.send(
            messages=[{"role": "user", "content": "Hallo"}], system="sys",
            use_high_tier=True,
        )
        self.assertEqual(captured["model"], "mistral-medium-2508")

    def test_rate_limit_falls_back_to_low_tier_model(self):
        import io
        import urllib.error

        provider = MistralProvider(
            model="mistral-small-2506",
            max_retries=0,
            difficulty_tiers={"low": "ministral-3b-2512", "medium": "mistral-small-2506", "high": "mistral-small-2506"},
        )
        call_models: list[str] = []

        def fake_urlopen(req, timeout=None):
            payload = json.loads(req.data)
            call_models.append(payload["model"])
            if payload["model"] == "mistral-small-2506":
                raise urllib.error.HTTPError(
                    req.full_url, 429, "rate limited", {}, io.BytesIO(b"{}")
                )
            return io.BytesIO(json.dumps({
                "choices": [{"message": {"content": "ok", "tool_calls": []}}]
            }).encode("utf-8"))

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = provider.send(messages=[{"role": "user", "content": "Hallo"}], system="sys")

        self.assertEqual(call_models, ["mistral-small-2506", "ministral-3b-2512"])
        self.assertEqual(result.text, "ok")


class FallbackProviderTests(unittest.TestCase):
    """Tests for the multi-provider fallback chain."""

    def test_uses_first_provider_when_it_succeeds(self):
        first = _FakeProvider("first")
        second = _FakeProvider("second")
        fallback = FallbackProvider([first, second])
        response = fallback.send([], "system")
        self.assertEqual(response.text, "first")

    def test_falls_back_when_first_provider_fails(self):
        first = _FailingProvider("boom")
        second = _FakeProvider("second")
        fallback = FallbackProvider([first, second])
        response = fallback.send([], "system")
        self.assertEqual(response.text, "second")
        self.assertEqual(fallback._current_index, 1)

    def test_send_tool_result_also_falls_back(self):
        first = _FailingProvider("boom")
        second = _FakeProvider("tool_result")
        fallback = FallbackProvider([first, second])
        response = fallback.send_tool_result([], "system")
        self.assertEqual(response.text, "tool_result")

    def test_raises_when_all_providers_fail(self):
        fallback = FallbackProvider([_FailingProvider("a"), _FailingProvider("b")])
        with self.assertRaises(RuntimeError):
            fallback.send([], "system")

    def test_supports_tools_only_if_all_providers_support_tools(self):
        tool_provider = _FakeProvider("tool")
        no_tool_provider = _NoToolProvider("no_tool")
        fallback = FallbackProvider([tool_provider, no_tool_provider])
        self.assertFalse(fallback.supports_tools)


class ResponseGuardTests(unittest.TestCase):
    """Tests for the anti-farewell guard and exit phrase detection."""

    def test_desktop_sentence_is_not_exit(self):
        """The user's example sentence must not be interpreted as goodbye."""
        self.assertFalse(
            is_exit("ja, ich stelle mir eine Bauanleitung, lege sie auf meinem Desktop ab")
        )

    def test_explicit_goodbye_is_exit(self):
        self.assertTrue(is_exit("auf Wiedersehen"))
        self.assertTrue(is_exit("tschüss"))
        self.assertTrue(is_exit("beenden"))

    def test_guard_replaces_farewell_for_non_exit_user(self):
        text = "Auf Wiedersehen, Sir. Es war mir ein Vergnügen."
        guarded = guard_response(text, "erstelle eine Bauanleitung")
        self.assertNotEqual(guarded, text)
        self.assertIn("kann diese Anfrage nicht direkt umsetzen", guarded)

    def test_guard_allows_farewell_after_goodbye(self):
        text = "Auf Wiedersehen, Sir."
        self.assertEqual(guard_response(text, "auf Wiedersehen"), text)

    def test_guard_leaves_normal_response_unchanged(self):
        text = "Ich erstelle die Bauanleitung und lege sie auf den Desktop."
        self.assertEqual(guard_response(text, "erstelle eine Bauanleitung"), text)


class FileToolTests(unittest.TestCase):
    """Tests for the file system tools."""

    def _temp_dir(self):
        """Create a temporary directory inside the user home (sandbox requirement)."""
        return tempfile.TemporaryDirectory(dir=str(Path.home()))

    def test_write_and_read_file(self):
        with self._temp_dir() as tmp:
            path = Path(tmp) / "test.txt"
            self.assertIn("Datei erstellt", write_file(str(path), "Hallo TARNO"))
            self.assertEqual(path.read_text(encoding="utf-8"), "Hallo TARNO")
            self.assertEqual(read_file(str(path)), "Hallo TARNO")

    def test_list_directory(self):
        with self._temp_dir() as tmp:
            Path(tmp, "a.txt").write_text("a", encoding="utf-8")
            Path(tmp, "b").mkdir()
            result = list_directory(tmp)
            self.assertIn("[FILE] a.txt", result)
            self.assertIn("[DIR] b", result)

    def test_write_file_outside_home_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "blocked.txt"
            result = write_file(str(path), "blocked")
            self.assertIn("Sicherheitshalber", result)
            self.assertFalse(path.exists())


class WakeWordConfigDefaultsTests(unittest.TestCase):
    """Tests for wake-word defaults loaded from config/default.yaml."""

    def test_default_wakeword_uses_tarno_model(self):
        config = TarnoConfig.load()
        self.assertEqual(config.wakeword.model_name, "jarvis")
        self.assertEqual(config.wakeword.patience, 1)
        self.assertEqual(config.wakeword.threshold, 0.10)
        self.assertEqual(config.wakeword.backend, "vosk")
        self.assertIn("jarvis", config.wakeword.wake_phrases)
        self.assertIn("hey tarno", config.wakeword.wake_phrases)


if __name__ == "__main__":
    unittest.main()
