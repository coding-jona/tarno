"""Conversation history management — provider-agnostic."""

from __future__ import annotations

import json
import logging
from collections import deque
from datetime import date, datetime
from pathlib import Path, PurePath
from typing import TYPE_CHECKING, Any
from uuid import UUID

from tarno_backend.ai.prompts import build_system_prompt
from tarno_backend.core.config import MemoryConfig, TTSPromptConfig
from tarno_backend.memory.knowledge_base import KnowledgeBase
from tarno_backend.memory.store import MemoryStore

if TYPE_CHECKING:
    from tarno_backend.ai.provider import LLMResponse

log = logging.getLogger(__name__)


def _serialize_value(obj: Any) -> Any:
    """Convert non-JSON-serializable objects into JSON-safe equivalents."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, (Path, PurePath)):
        return str(obj)
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return obj.to_dict()
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class _ConversationEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        return _serialize_value(obj)


# Tools whose result text is externally-sourced (file contents, directory
# listings, web output) rather than TARNO's own system-generated status
# messages — a malicious file name or file content could otherwise smuggle
# instructions into the LLM's context as if they came from the user/system.
_UNTRUSTED_CONTENT_TOOLS = frozenset({
    "read_file", "list_directory", "search_files", "web_search", "fetch_webpage",
    "browser_navigate", "browser_read", "browser_click",
})


def _wrap_untrusted(text: str) -> str:
    return f"<untrusted_data>\n{text}\n</untrusted_data>"


class ConversationManager:
    """Tracks the message history for an LLM conversation."""

    def __init__(
        self,
        max_history: int = 20,
        memory: MemoryConfig | None = None,
        memory_store: MemoryStore | None = None,
        knowledge_base: KnowledgeBase | None = None,
        tts_config: TTSPromptConfig | None = None,
    ) -> None:
        self._history: deque[dict[str, Any]] = deque(maxlen=max_history)
        self._memory = memory
        self._memory_store = memory_store
        self._knowledge_base = knowledge_base
        self._tts_config = tts_config
        self._workspace: dict[str, Any] | None = None
        self._chat_mode: str = "chat"
        # Kontext-Effizienz Phase 4: haelt die aktuell aktive rekursive
        # Zusammenfassung fuer den naechsten HistorySummarizer-Aufruf. Wird
        # NICHT als eigenes JSON-Feld persistiert (kein Schema-Change,
        # siehe _load()'s Rekonstruktion aus der synthetischen Nachricht),
        # sondern beim Laden aus der zuletzt gespeicherten
        # Zusammenfassungs-Nachricht zurueckgewonnen.
        self._current_summary: str | None = None
        self._load()

    @property
    def system_prompt(self) -> str:
        """Read-only, computed fresh on every access (system_prompt is
        already resent in full on every single LLM call - see
        PersonaGuard's module docstring) so the model always has ground
        truth for "today"."""
        return build_system_prompt(
            self._chat_mode, self._workspace, tts_config=self._tts_config
        )

    def set_workspace(self, workspace: dict[str, Any] | None) -> None:
        """Set the active workspace context that will be injected into the
        system prompt. Passing None clears the workspace state."""
        self._workspace = workspace

    def set_chat_mode(self, mode: str | None) -> None:
        """Set the chat mode ('chat' or 'code'). Unknown values fall back to 'chat'."""
        self._chat_mode = mode if mode in ("chat", "code") else "chat"

    def _memory_path(self) -> Path | None:
        if not self._memory or not self._memory.enabled:
            return None
        path = Path(self._memory.storage_dir).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path / f"{self._memory.conversation_id}.json"

    def _load(self) -> None:
        memory_path = self._memory_path()
        if not memory_path or not memory_path.exists():
            return
        try:
            raw = json.loads(memory_path.read_text(encoding="utf-8"))
            for msg in raw:
                self._history.append(msg)
            self._sanitize()
            self._current_summary = self._extract_persisted_summary()
            log.info("Konversationsverlauf aus %s geladen (%d Einträge)", memory_path, len(self._history))
        except Exception:
            log.exception("Konversationsverlauf konnte nicht geladen werden")

    def _save(self) -> None:
        memory_path = self._memory_path()
        if not memory_path:
            return
        try:
            memory_path.write_text(
                json.dumps(
                    list(self._history),
                    ensure_ascii=False,
                    indent=2,
                    cls=_ConversationEncoder,
                ),
                encoding="utf-8",
            )
        except Exception:
            log.exception("Konversationsverlauf konnte nicht gespeichert werden")

    def _sanitize(self) -> list[dict[str, Any]]:
        """Repair corrupted tool-use/tool-result order in memory.

        Tool results must immediately follow the assistant message that contains the
        matching tool_use block. Orphan tool results and tool_use blocks without
        matching results are removed.
        """
        messages = list(self._history)

        # Collect all tool_use ids from assistant messages
        assistant_tool_use_ids: set[str] = set()
        for msg in messages:
            if msg.get("role") != "assistant":
                continue
            content = msg.get("content", "")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        assistant_tool_use_ids.add(block.get("id"))

        # Collect tool_result blocks that belong to a known assistant tool_use
        result_by_id: dict[str, dict[str, Any]] = {}
        kept_messages: list[dict[str, Any]] = []

        for msg in messages:
            if msg.get("role") != "user":
                kept_messages.append(msg)
                continue
            content = msg.get("content", "")
            if isinstance(content, list):
                non_result_blocks: list[dict[str, Any]] = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tool_use_id = block.get("tool_use_id")
                        if tool_use_id in assistant_tool_use_ids:
                            result_by_id[tool_use_id] = block
                        else:
                            log.warning("Tool result ohne passendes tool_use entfernt: %s", tool_use_id)
                    else:
                        non_result_blocks.append(block)
                if non_result_blocks:
                    kept_messages.append({**msg, "content": non_result_blocks})
                # user messages containing only tool_result blocks are dropped
                continue
            kept_messages.append(msg)

        # Rebuild the history with tool results placed after the matching assistant
        sanitized: list[dict[str, Any]] = []
        for msg in kept_messages:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                if isinstance(content, list):
                    tool_use_ids = [b["id"] for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]
                    ordered_results = [result_by_id[tid] for tid in tool_use_ids if tid in result_by_id]

                    # Keep only tool_use blocks that have a matching result
                    filtered_content = [
                        b for b in content
                        if not (isinstance(b, dict) and b.get("type") == "tool_use" and b.get("id") not in result_by_id)
                    ]

                    if not filtered_content:
                        # Assistant was only tool_use blocks without results -> drop
                        continue

                    sanitized.append({**msg, "content": filtered_content})
                    for result in ordered_results:
                        sanitized.append({"role": "user", "content": [result]})
                    continue

            sanitized.append(msg)

        # Some providers (confirmed live: Gemini, "function call turn must
        # come immediately after a user turn or a function response turn")
        # reject two adjacent assistant messages with no intervening
        # user/tool-result turn - a shape the pairing repair above doesn't
        # prevent on its own. Merge any such run into the last assistant
        # message in the run so the sequence always alternates from a
        # provider's point of view. Harmless for providers without this
        # constraint, so enforced unconditionally rather than per-provider.
        deduped: list[dict[str, Any]] = []
        for msg in sanitized:
            if (
                deduped
                and msg.get("role") == "assistant"
                and deduped[-1].get("role") == "assistant"
            ):
                prev_content = deduped[-1].get("content", [])
                cur_content = msg.get("content", [])
                if not isinstance(prev_content, list):
                    prev_content = [{"type": "text", "text": str(prev_content)}]
                if not isinstance(cur_content, list):
                    cur_content = [{"type": "text", "text": str(cur_content)}]
                deduped[-1] = {**deduped[-1], "content": prev_content + cur_content}
                continue
            deduped.append(msg)

        self._history.clear()
        self._history.extend(deduped)
        return deduped

    def add_user_message(self, text: str, image_data_url: str | None = None) -> None:
        """Append a user turn, optionally with an attached image."""
        if image_data_url:
            # Content-Block-Liste statt String (Phase A: Bild-Upload) - folgt
            # demselben Muster wie add_assistant_response/add_assistant_tool_use.
            content: Any = [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ]
        else:
            content = text
        self._history.append({"role": "user", "content": content})
        self._save()

    def inject_relevant_memory(self, query: str, limit: int = 5) -> bool:
        """Retrieve relevant memory and prepend it as context if any is found."""
        if self._memory_store is None:
            return False

        from tarno_backend.memory.retrieval import MemoryRetriever

        retriever = MemoryRetriever(self._memory_store)
        memories = retriever.retrieve(query, limit=limit)
        if not memories:
            return False

        lines = ["Relevante Informationen aus dem Langzeitgedächtnis:"]
        for memory in memories:
            lines.append(f"- {memory.content}")
        context = "\n".join(lines)

        self._history.append({"role": "system", "content": context})
        self._save()
        return True

    def inject_relevant_kb(self, query: str, top_k: int = 5) -> bool:
        """Retrieve relevant knowledge-base chunks and prepend them as context."""
        if self._knowledge_base is None or self._chat_mode != "code":
            return False
        chunks = self._knowledge_base.search(query, top_k=top_k)
        if not chunks:
            return False
        lines = ["Relevante Informationen aus der Wissensbasis:"]
        for text, score in chunks:
            lines.append(f"- {text}")
        context = "\n".join(lines)
        self._history.append({"role": "system", "content": context})
        self._save()
        return True

    def inject_persona_reminder(self, text: str) -> None:
        """Insert a persona/safety re-anchoring reminder into the history
        (Block 4, Phase 34) - positioned close to the generation point,
        unlike the system prompt which is sent once per call but doesn't
        gain positional recency in a long history."""
        self._history.append({"role": "system", "content": text})
        self._save()

    def add_system_reminder(self, text: str) -> None:
        """Append an arbitrary system reminder to the active conversation."""
        self._history.append({"role": "system", "content": text})
        self._save()

    def remember_fact(self, key: str, value: str, source: str = "user") -> None:
        """Persist a fact to the long-term memory store, with a semantic
        embedding (Block 4, Phase 31) so it's findable by meaning later, not
        just by exact keyword match."""
        if self._memory_store is None:
            return
        from tarno_backend.memory.embeddings import get_default_provider
        embedding = get_default_provider().embed_one(f"{key}: {value}")
        self._memory_store.save_fact(key, value, source, embedding=embedding)

    def add_assistant_response(self, text: str) -> None:
        """Add a plain text assistant response."""
        self._history.append({
            "role": "assistant",
            "content": [{"type": "text", "text": text}],
        })
        self._save()

    def add_assistant_tool_use(self, response: LLMResponse) -> None:
        """Add an assistant message that contains tool calls (for the tool_use flow)."""
        content: list[dict[str, Any]] = []
        if response.text:
            content.append({"type": "text", "text": response.text})
        for tc in response.tool_calls:
            block: dict[str, Any] = {
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.input,
            }
            if tc.raw_extra:
                block["provider_extra"] = tc.raw_extra
            content.append(block)
        self._history.append({"role": "assistant", "content": content})
        self._save()

    def add_tool_result(self, tool_use_id: str, result: str, tool_name: str | None = None) -> None:
        content = _wrap_untrusted(result) if tool_name in _UNTRUSTED_CONTENT_TOOLS else result
        self._history.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": content,
                }
            ],
        })
        self._save()

    def get_messages(self) -> list[dict[str, Any]]:
        """Return the current history as a plain list, re-sanitizing first
        so a caller never sees a broken tool-use/tool-result pairing."""
        self._sanitize()
        return list(self._history)

    def replace_with_summary(self, summary_text: str, keep_last: int = 5) -> None:
        """Replace older messages with a summary and preserve the last N messages."""
        self._sanitize()
        recent = list(self._history)[-keep_last:] if keep_last > 0 else []
        self._history.clear()
        self._history.append({
            "role": "user",
            "content": f"{self._SUMMARY_PREFIX}:\n{summary_text}",
        })
        self._history.extend(recent)
        self._save()

    # Kontext-Effizienz Phase 4: gemeinsames Praefix, damit _load() eine
    # persistierte Zusammenfassung (ob per replace_with_summary oder
    # replace_with_recursive_summary erzeugt) wiedererkennt, ohne das
    # JSON-Schema um ein eigenes Feld zu erweitern.
    _SUMMARY_PREFIX = "Zusammenfassung der bisherigen Konversation"

    def replace_with_recursive_summary(self, new_summary_text: str, keep_last: int = 5) -> None:
        """Wie replace_with_summary, aber merkt sich new_summary_text als
        _current_summary fuer den naechsten rekursiven Zusammenfassungs-
        Aufruf (HistorySummarizer.summarize faltet diese vorherige
        Zusammenfassung dann ein, statt sie zu verwerfen - siehe
        tarno/ai/context/summarizer.py)."""
        self._sanitize()
        recent = list(self._history)[-keep_last:] if keep_last > 0 else []
        self._history.clear()
        self._history.append({
            "role": "user",
            "content": f"{self._SUMMARY_PREFIX} (rekursiv aktualisiert):\n{new_summary_text}",
        })
        self._history.extend(recent)
        self._current_summary = new_summary_text
        self._save()

    def get_current_summary_for_debug(self) -> str | None:
        """Read-only Zugriff auf die aktuell aktive Zusammenfassung, fuer
        das aggressive Debug-Logging (Kontext-Effizienz Phase 6)."""
        return self._current_summary

    def _extract_persisted_summary(self) -> str | None:
        """Rekonstruiert _current_summary aus der zuletzt geladenen
        synthetischen Zusammenfassungs-Nachricht, falls vorhanden - ueberlebt
        so Neustarts ohne eigenes JSON-Envelope-Feld."""
        for msg in reversed(self._history):
            if msg.get("role") != "user":
                continue
            content = msg.get("content")
            if not isinstance(content, str) or not content.startswith(self._SUMMARY_PREFIX):
                continue
            _, _, text = content.partition(":\n")
            return text or None
        return None

    def clear(self) -> None:
        """Wipe the entire conversation history and persist the empty state."""
        self._history.clear()
        self._save()
