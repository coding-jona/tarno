"""Simple synchronous event bus for loose coupling between modules."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger(__name__)

EventHandler = Callable[..., None]


@dataclass
class Event:
    """Base class for all events."""
    pass


@dataclass
class WakeWordDetectedEvent(Event):
    pass


@dataclass
class SpeechRecognizedEvent(Event):
    text: str = ""


@dataclass
class ResponseReadyEvent(Event):
    text: str = ""
    tool_calls: list[str] = field(default_factory=list)
    chat_id: str = ""
    turn_id: str = ""


@dataclass
class StreamingDeltaEvent(Event):
    text: str = ""
    is_finished: bool = False


@dataclass
class StreamingFinishedEvent(Event):
    text: str = ""


@dataclass
class ErrorEvent(Event):
    error: Exception | None = None
    module: str = ""


@dataclass
class TtsStartedEvent(Event):
    """Emitted when the synthesizer starts playback of a spoken response.
    `envelope`/`duration_seconds` carry the real amplitude envelope of the
    already-synthesized audio, precomputed once (not streamed live), so the
    UI can drive a whole-body Orb resonance animation genuinely in sync with
    what TARNO is saying rather than a generic procedural loop."""
    text: str = ""
    envelope: list[float] = field(default_factory=list)
    duration_seconds: float = 0.0


@dataclass
class TtsFinishedEvent(Event):
    """Emitted when the synthesizer finishes playback."""
    pass


@dataclass
class VoiceErrorEvent(Event):
    """Emitted when an LLM turn came back as a synthetic error placeholder
    (rate limit exhausted, API error, network unreachable) rather than a
    real answer - lets the gRPC bridge flash the Voice-Orb to "error"
    without conflating this with ErrorEvent's hard-crash/exception case."""
    message: str = ""


@dataclass
class ContextUsageEvent(Event):
    """Emitted after an LLM turn that reported token usage, so the UI can
    show a context-window indicator. Not emitted if the provider/turn
    didn't report usage (e.g. tool-result follow-ups on some providers)."""
    tokens_used: int = 0
    context_window: int = 0


@dataclass
class VisionAttachmentEvent(Event):
    """Emitted after a successful describe_what_i_see tool call, carrying
    the exact JPEG frame that was analysed by the vision model. The gRPC
    server can forward this to the UI so the user sees what TARNO saw."""
    image_bytes: bytes = b""
    source: str = "camera"  # 'camera' | 'screenshot' | etc.


@dataclass
class ProcessingStageEvent(Event):
    """A real, in-progress pipeline stage during one turn - replaces the old
    static "Denkt nach..." placeholder (found via live testing to be
    entirely fake, shown identically regardless of what the backend was
    actually doing). `detail` is pre-formatted German display text for the
    "llm_call"/"tool_exec"/"tool_followup" stages; `reasoning` carries a
    captured <think>...</think> block for the "reasoning" stage instead."""
    stage: str = ""
    detail: str = ""
    reasoning: str = ""


@dataclass
class AgentTraceEvent(Event):
    """Live trace event for the coding agent (thought, tool, diff)."""
    turn_id: str = ""
    chat_id: str = ""
    trace_id: str = ""
    parent_id: str = ""
    trace_type: str = ""  # thought_delta | tool_start | tool_end | file_diff
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class CodingOutputEvent(Event):
    """Emitted by the coding backend for each live output chunk."""
    kind: str = ""
    text: str = ""
    timestamp_ms: int = 0
    chat_id: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class MeshNodeSeenEvent(Event):
    """Emitted whenever a mesh node (secondary phone, ESP32 scanner, hub
    phone) is heard from - either a heartbeat or any telemetry packet."""
    sender_node: str = ""
    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


@dataclass
class MeshHubChangedEvent(Event):
    """Emitted when MeshRouter's active hub role changes."""
    active_hub: str = ""  # "HUB" | "PC_FALLBACK" | "NONE"
    reason: str = ""


@dataclass
class MeshScenarioChangedEvent(Event):
    """Emitted when MeshRouter's 4-scenario state machine transitions."""
    scenario: str = ""  # "FULL_MESH" | "PC_FALLBACK" | "SOLO_PC"
    previous: str = ""


class EventBus:
    """Synchronous publish/subscribe event dispatcher."""

    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type[Event], handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: Event) -> None:
        for handler in self._handlers.get(type(event), []):
            try:
                handler(event)
            except Exception:
                log.exception("Event-Handler-Fehler für %s", type(event).__name__)
