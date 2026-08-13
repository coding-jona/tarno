"""TARNO agent service that runs on the OpenVoiceOS bus with LLM and tools."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from ovos_bus_client import MessageBusClient
from ovos_bus_client.message import Message

from tarno_backend.ai.conversation import ConversationManager
from tarno_backend.ai.factory import create_provider_with_fallback as _create_provider
from tarno_backend.ai.provider import LLMResponse
from tarno_backend.core.action_result import ActionResult
from tarno_backend.ai.response_guard import guard_response
from tarno_backend.ai.tool_registry import ToolDefinition, ToolRegistry
from tarno_backend.utils.text import is_exit
from tarno_backend.browser.web_control import web_search
from tarno_backend.core.calendar_service import get_calendar_events
from tarno_backend.core.command_tool import CommandTool
from tarno_backend.core.config import TarnoConfig
from tarno_backend.extensions.coordinator import ExtensionCoordinator
from tarno_backend.memory.store import MemoryStore
from tarno_backend.telemetry.logging import new_correlation_id, set_correlation_id
from tarno_backend.desktop.app_control import open_application
from tarno_backend.desktop.file_manager import (
    copy_file,
    create_directory,
    delete_file,
    list_directory,
    move_file,
    open_file,
    read_file,
    search_files,
    write_file,
)
from tarno_backend.desktop.screenshot import take_screenshot
from tarno_backend.desktop.system_info import get_system_info

log = logging.getLogger(__name__)


class AgentService:
    """TARNO agent wired to the OpenVoiceOS message bus."""

    def __init__(self, bus: MessageBusClient, config: TarnoConfig | None = None) -> None:
        set_correlation_id(new_correlation_id())
        self._bus = bus
        self._config = config or TarnoConfig.load()
        self._provider = _create_provider(self._config)
        memory_store: MemoryStore | None = None
        if self._config.memory.enabled:
            memory_path = Path(self._config.memory.storage_dir).expanduser() / "memory.db"
            memory_store = MemoryStore(memory_path)
        self._conversation = ConversationManager(
            self._config.llm.max_history,
            memory=self._config.memory,
            memory_store=memory_store,
            tts_config=self._config.audio.tts_prompt,
        )
        self._tools = ToolRegistry()
        self._register_default_tools()

        def _request_task_approval(task) -> bool | None:
            self._bus.emit(Message(
                "tarno.task.approval.request",
                data={"task_id": task.id, "description": task.description},
            ))
            return None

        self._extensions = ExtensionCoordinator(
            tool_executor=self._tools.execute,
            reminder_callback=lambda msg: self._speak(msg),
            approval_callback=_request_task_approval,
        )
        if self._config.briefing.enabled:
            self._extensions.set_briefing_times(
                self._config.briefing.times,
                self._run_briefing,
            )

    def _register_default_tools(self) -> None:
        """Register the default toolset available to TARNO."""
        self._tools.register(ToolDefinition(
            name="open_application",
            description="Öffnet eine Anwendung auf dem Computer (z.B. Notepad, Chrome, Calculator)",
            input_schema={"type": "object", "properties": {"app_name": {"type": "string"}}, "required": ["app_name"]},
            handler=open_application,
        ))
        self._tools.register(ToolDefinition(
            name="open_file",
            description="Öffnet eine Datei mit der Standard-Anwendung",
            input_schema={"type": "object", "properties": {"filepath": {"type": "string"}}, "required": ["filepath"]},
            handler=open_file,
        ))
        self._tools.register(ToolDefinition(
            name="web_search",
            description="Öffnet den Browser mit einer URL oder führt eine Google-Suche durch",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            handler=web_search,
        ))
        self._tools.register(ToolDefinition(
            name="get_system_info",
            description="Gibt Systeminformationen zurück (OS, CPU, RAM, Festplatte)",
            input_schema={"type": "object", "properties": {}},
            handler=lambda: get_system_info(),
        ))
        self._tools.register(ToolDefinition(
            name="get_calendar_events",
            description="Gibt die heutigen und kommenden Kalendertermine zurück",
            input_schema={"type": "object", "properties": {}},
            handler=lambda: get_calendar_events(self._config.briefing.calendar_file, self._config.briefing.calendar_days),
        ))
        self._tools.register(ToolDefinition(
            name="take_screenshot",
            description="Erstellt einen Screenshot des Bildschirms",
            input_schema={"type": "object", "properties": {}},
            handler=lambda: take_screenshot(),
        ))
        self._tools.register(ToolDefinition(
            name="search_files",
            description="Sucht Dateien in einem Verzeichnis nach Muster (z.B. '*.pdf', '*.docx')",
            input_schema={"type": "object", "properties": {"directory": {"type": "string"}, "pattern": {"type": "string"}}, "required": ["directory", "pattern"]},
            handler=search_files,
        ))
        self._tools.register(ToolDefinition(
            name="read_file",
            description="Liest den Inhalt einer Textdatei",
            input_schema={"type": "object", "properties": {"filepath": {"type": "string"}}, "required": ["filepath"]},
            handler=read_file,
        ))
        self._tools.register(ToolDefinition(
            name="write_file",
            description="Schreibt einen Text in eine Datei (nur unter dem Benutzer-Home-Verzeichnis).",
            input_schema={"type": "object", "properties": {"filepath": {"type": "string", "description": "Zielpfad zur Datei, z.B. ~/Desktop/anleitung.txt"}, "content": {"type": "string", "description": "Inhalt der Datei"}}, "required": ["filepath", "content"]},
            handler=write_file,
        ))
        self._tools.register(ToolDefinition(
            name="list_directory",
            description="Listet Dateien und Verzeichnisse in einem Verzeichnis auf (nur unter dem Benutzer-Home-Verzeichnis).",
            input_schema={"type": "object", "properties": {"path": {"type": "string", "description": "Pfad zum Verzeichnis, z.B. ~/Desktop"}}, "required": ["path"]},
            handler=list_directory,
        ))
        self._tools.register(ToolDefinition(
            name="create_directory",
            description="Erstellt ein neues Verzeichnis (inkl. Unterverzeichnisse)",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            handler=create_directory,
        ))
        self._tools.register(ToolDefinition(
            name="copy_file",
            description="Kopiert eine Datei an einen neuen Ort",
            input_schema={"type": "object", "properties": {"source": {"type": "string"}, "destination": {"type": "string"}}, "required": ["source", "destination"]},
            handler=copy_file,
        ))
        self._tools.register(ToolDefinition(
            name="move_file",
            description="Verschiebt eine Datei an einen neuen Ort",
            input_schema={"type": "object", "properties": {"source": {"type": "string"}, "destination": {"type": "string"}}, "required": ["source", "destination"]},
            handler=move_file,
        ))
        self._tools.register(ToolDefinition(
            name="delete_file",
            description="Löscht eine Datei (Vorsicht — unwiderruflich)",
            input_schema={"type": "object", "properties": {"filepath": {"type": "string"}}, "required": ["filepath"]},
            handler=delete_file,
        ))

        command_tool = CommandTool(self._config)
        self._tools.register(ToolDefinition(
            name="execute_command",
            description=(
                "Führt einen validierten Shell-Befehl aus. Nicht für direkte "
                "Nutzung gedacht — das LLM sollte vorher den Intent beschreiben."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "intent": {"type": "string"},
                    "shell": {"type": "string", "enum": ["powershell", "cmd", "bash"], "default": "powershell"},
                    "command": {"type": "string"},
                    "params": {"type": "object"},
                    "explanation": {"type": "string"},
                    "user_query": {"type": "string"},
                },
                "required": ["intent", "command"],
            },
            handler=command_tool,
        ))

        self._tools.register(ToolDefinition(
            name="plan_task",
            description=(
                "Plant eine mehrstufige Aufgabe, die vor Ausführung vom Nutzer "
                "genehmigt werden muss. Schritte sind JSON-Objekte mit 'tool' und 'params'."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "tool": {"type": "string"},
                                "params": {"type": "object"},
                            },
                            "required": ["tool"],
                        },
                    },
                },
                "required": ["description", "steps"],
            },
            handler=self._plan_task,
        ))

        log.info("%d Tools registriert", len(self._tools.get_tool_schemas()))

    def _plan_task(self, description: str, steps: list[dict[str, Any]]) -> ActionResult:
        task = self._extensions.task_planner.create(description, steps)
        self._bus.emit(Message(
            "tarno.task.approval.request",
            data={"task_id": task.id, "description": task.description},
        ))
        return ActionResult(
            success=True,
            message=f"Aufgabe geplant: {description}. Genehmigung angefordert.",
            details={"task_id": task.id},
        )

    def start(self) -> None:
        """Subscribe to OVOS bus events."""
        self._bus.on("recognizer_loop:utterance", self._handle_utterance)
        self._bus.on("tarno.task.approval.grant", self._on_task_approval_grant)
        self._bus.on("tarno.task.approval.deny", self._on_task_approval_deny)
        self._extensions.start()
        log.info("TARNO Agent Service gestartet")

    def stop(self) -> None:
        """Unsubscribe from OVOS bus events."""
        self._bus.remove("recognizer_loop:utterance", self._handle_utterance)
        self._bus.remove("tarno.task.approval.grant", self._on_task_approval_grant)
        self._bus.remove("tarno.task.approval.deny", self._on_task_approval_deny)
        self._extensions.stop()
        log.info("TARNO Agent Service gestoppt")

    def _on_task_approval_grant(self, message: Message) -> None:
        task_id = message.data.get("task_id")
        if task_id:
            self._extensions.task_planner.approve(task_id)

    def _on_task_approval_deny(self, message: Message) -> None:
        task_id = message.data.get("task_id")
        if task_id:
            self._extensions.task_planner.reject(task_id)

    def _handle_utterance(self, message: Message) -> None:
        """Process a transcribed utterance and emit a spoken response."""
        try:
            utterances = message.data.get("utterances", [])
            if not utterances:
                return
            user_text = utterances[0]
            log.info("Nutzer: %s", user_text)

            if is_exit(user_text):
                self._speak("Auf Wiedersehen, Sir. Es war mir ein Vergnügen.")
                return

            routine_result = self._extensions.try_routine(user_text)
            if routine_result is not None:
                self._conversation.add_assistant_response(routine_result.message)
                self._speak(routine_result.message)
                return

            self._conversation.add_user_message(user_text)
            self._conversation.inject_relevant_memory(user_text)
            self._emit_status("Denkt nach...")
            response = self._provider.send(
                messages=self._conversation.get_messages(),
                system=self._conversation.system_prompt,
                tools=self._tools.get_tool_schemas() if self._provider.supports_tools else None,
            )
            spoken = self._process_response(response, user_text)
            if spoken:
                self._speak(spoken)
        except Exception:
            log.exception("Agent-Verarbeitungsfehler")
            self._emit_status("Fehler")
            self._speak("Entschuldigung, Sir. Es gab einen Verarbeitungsfehler.")

    def _emit_status(self, state: str) -> None:
        """Emit a status message on the bus for the UI."""
        self._bus.emit(Message("tarno.status", data={"state": state}))

    def _run_briefing(self) -> None:
        try:
            response = self._provider.send(
                messages=[{"role": "user", "content": self._config.briefing.prompt}],
                system=self._conversation.system_prompt,
                tools=self._tools.get_tool_schemas() if self._provider.supports_tools else None,
            )
            self._speak(guard_response(response.text))
        except Exception:
            log.exception("Briefing fehlgeschlagen")

    def _process_response(self, response: LLMResponse, user_text: str = "") -> str:
        """Process an LLM response, execute any tool calls, and continue until the assistant answers."""
        max_iterations = 5
        for _ in range(max_iterations):
            if not response.tool_calls:
                self._conversation.add_assistant_response(response.text)
                return guard_response(response.text, user_text)

            # Add the assistant message with the tool calls to history first,
            # then the tool result messages so the role order is correct.
            self._conversation.add_assistant_tool_use(response)

            # Execute all tool calls requested in this response
            for tc in response.tool_calls:
                result = self._tools.execute(tc.name, tc.input)
                result_text = (
                    json.dumps(result.to_dict(), ensure_ascii=False)
                    if isinstance(result, ActionResult)
                    else str(result)
                )
                self._conversation.add_tool_result(tc.id, result_text, tool_name=tc.name)

            # Ask the LLM for the next step with the tool results
            try:
                response = self._provider.send(
                    messages=self._conversation.get_messages(),
                    system=self._conversation.system_prompt,
                    tools=self._tools.get_tool_schemas() if self._provider.supports_tools else None,
                )
            except Exception:
                log.exception("LLM Followup-Fehler")
                return guard_response("Entschuldigung, Sir. Die Tool-Ausführung ist fehlgeschlagen.", user_text)

        return guard_response("Entschuldigung, Sir. Zu viele Tool-Schritte erforderlich.", user_text)

    def speak(self, text: str) -> None:
        """Send a speak message to the bus."""
        self._bus.emit(Message("speak", data={"utterance": text, "lang": self._config.language}))

    def _speak(self, text: str) -> None:
        """Send a speak message to the bus."""
        self.speak(text)

    def trigger_briefing(self) -> None:
        """Generate and speak a proactive briefing."""
        try:
            system_info = self._tools.execute("get_system_info", {})
            calendar_info = self._tools.execute("get_calendar_events", {})
            now = datetime.now().strftime("%H:%M")
            prompt = (
                f"{self._config.briefing.prompt}\n\n"
                f"Aktuelle Uhrzeit: {now}\n"
                f"Systeminformationen: {system_info}\n"
                f"Kalender: {calendar_info}"
            )

            briefing_text = "Gib mir ein kurzes Briefing."
            self._conversation.add_user_message(briefing_text)
            response = self._provider.send(
                messages=self._conversation.get_messages(),
                system=prompt,
            )
            spoken = self._process_response(response, briefing_text)
            if spoken:
                self.speak(spoken)
                log.info("Briefing ausgesprochen")
        except Exception:
            log.exception("Briefing-Generierung fehlgeschlagen")
            self.speak("Entschuldigung, Sir. Das Briefing konnte nicht erstellt werden.")

