"""PoolWorker: kapselt einen LLMProvider fuer einen Agent-Pool-Slot
(Coding-Agent-Pool-Plan, Phase 1).

Ein PoolWorker fuehrt genau einen Agenten-Slot aus (Lead ODER Worker - die
Rolle steckt in PoolAgentSpec.role, siehe pool_system.py fuer die jeweiligen
System-Prompts). LLMProvider.send() ist synchron/blockierend; run_subtask()
laeuft deshalb ueber loop.run_in_executor() in einem vom Aufrufer
uebergebenen Executor, damit der Orchestrator (Phase 2) mehrere Worker via
asyncio.gather() echt parallel ausfuehren kann, ohne den bestehenden
Einzel-Agent-Coding-Executor (_coding_executor, max_workers=1) zu
beeintraechtigen.

Live-Test (Kontext-Effizienz-Plan-Nachtrag) zeigte: Worker bekamen bisher
NUR Dateinamen als Text, nie Dateiinhalt oder Tool-Zugriff (tools=None) -
jede Revisionsrunde wiederholte dadurch dieselbe "brauche Code"-Antwort.
Dieses Modul gibt Lead UND Workern jetzt read-only Tools (read_file,
list_directory - kein Schreibzugriff, bestaetigte Architektur-Entscheidung
bleibt unangetastet) mit einer kompakten Tool-Calling-Schleife nach dem
Vorbild von tarno/core/engine.py::_process_response, aber ohne
ConversationManager - die Pool-Nachrichtenliste ist ephemer fuer genau
diesen einen Aufruf.

Zweiter Live-Fund (LagTestPlugin-Test, Java/PaperMC-Projekt): ohne explizit
vom Nutzer angegebene fnames UND ohne jede Erwaehnung des Workspace-Pfads im
Prompt hatte das Modell schlicht keinen Anhaltspunkt, in welchem Projekt/
welcher Sprache es arbeitet, und ist auf generische Trainings-Assoziationen
(Python/GitHub-Workflows) zurueckgefallen. _workspace_label() liefert jetzt
IMMER eine Grundierungszeile (Name + Pfad), unabhaengig von fnames, und
list_directory gibt dem Modell einen echten Weg, die tatsaechliche
Projektstruktur selbst zu erkunden statt zu raten.
"""

from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import Executor
from typing import TYPE_CHECKING, Any

from tarno.ai.factory import create_provider
from tarno.ai.pool.models import PoolAgentSpec, PoolMessage, SubTask
from tarno.ai.prompts.pool_system import WORKER_SYSTEM_PROMPT
from tarno.ai.tool_registry import ToolDefinition, ToolRegistry
from tarno.desktop.file_manager import list_directory, read_file

if TYPE_CHECKING:
    from tarno.ai.provider import LLMProvider
    from tarno.core.config import TarnoConfig

log = logging.getLogger(__name__)


def workspace_label(workspace: dict[str, Any] | None) -> str:
    """Liefert eine kurze, immer vorhandene Grundierungszeile ("wo arbeite
    ich gerade") fuer Lead- und Worker-Prompts - unabhaengig davon, ob
    fnames explizit angegeben wurden. Ohne diese Zeile hat das Modell keinen
    Anhaltspunkt zum tatsaechlichen Projekt und faellt auf generische
    Trainings-Annahmen zurueck (live bestaetigt: Python/GitHub-Vorschlaege
    fuer ein Java/PaperMC-Projekt)."""
    if not workspace:
        return ""
    name = workspace.get("name") or ""
    root_path = workspace.get("root_path") or ""
    if not root_path and workspace.get("folders"):
        first = workspace["folders"][0]
        root_path = first.get("path", "") if isinstance(first, dict) else ""
    if not name and not root_path:
        return ""
    return f"Workspace: {name} ({root_path})".strip()


def _build_read_only_tools(workspace: dict[str, Any] | None) -> ToolRegistry | None:
    """Baut ein bewusst minimales, read-only Tool-Set - read_file und
    list_directory, keine Schreib-/Ausfuehrungs-Tools (bestaetigte
    Architektur-Entscheidung: Pool-Agenten haben keine Schreibrechte). None
    ohne Workspace, da beide Tools ohne Workspace-Root nichts sinnvoll
    aufloesen koennen."""
    if not workspace:
        return None
    registry = ToolRegistry()
    registry.register(ToolDefinition(
        name="read_file",
        description=(
            "Liest den Inhalt einer Textdatei im aktiven Workspace (nur lesend). "
            "Relative Pfade werden gegen den Workspace-Root aufgelöst."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Pfad zur Datei (relativ zum Workspace-Root)"},
            },
            "required": ["filepath"],
        },
        handler=lambda filepath: read_file(filepath, workspace=workspace),
    ))
    registry.register(ToolDefinition(
        name="list_directory",
        description=(
            "Listet Dateien und Unterordner eines Verzeichnisses im aktiven Workspace "
            "auf (nur lesend). Leerer Pfad oder '.' listet die Workspace-Wurzel(n) auf - "
            "damit kann die tatsächliche Projektstruktur erkundet werden, statt sie zu erraten."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Verzeichnispfad (relativ zum Workspace-Root, leer für die Wurzel)"},
            },
            "required": [],
        },
        handler=lambda path="": list_directory(path, workspace=workspace),
    ))
    return registry


def run_with_tool_loop(
    provider: "LLMProvider",
    prompt: str,
    system: str,
    workspace: dict[str, Any] | None,
    max_iterations: int,
) -> str:
    """Synchron (soll bereits im Executor-Thread laufen): send() -> falls
    Tool-Calls, ausfuehren und send_tool_result() erneut aufrufen, bis keine
    Tool-Calls mehr kommen oder das Iterationslimit erreicht ist. Baut die
    Nachrichtenliste manuell (statt ueber ConversationManager), da ein
    Pool-Aufruf ephemer ist und keine Persistenz braucht - Nachrichtenform
    mirrort ConversationManager.add_assistant_tool_use/add_tool_result
    (tarno/ai/conversation.py), damit sie von jedem Provider gleich
    interpretiert wird. Von PoolWorker.run_subtask (Worker) UND
    PoolOrchestrator._call_provider (Lead) gemeinsam genutzt, damit beide
    Rollen dieselbe Tool-Faehigkeit haben."""
    tools = _build_read_only_tools(workspace)
    tool_schemas = tools.get_tool_schemas() if tools and provider.supports_tools else None

    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    response = provider.send(messages=messages, system=system, tools=tool_schemas)

    if tools is None:
        # Kein Workspace uebergeben (z.B. Tests) - response ist ggf. ein
        # einfaches Mock-Objekt ohne .tool_calls; response.tool_calls hier
        # NICHT anfassen.
        return response.text.strip()

    max_iterations = max(1, max_iterations)
    for _ in range(max_iterations):
        if not response.tool_calls:
            break

        content: list[dict[str, Any]] = []
        if response.text:
            content.append({"type": "text", "text": response.text})
        for tc in response.tool_calls:
            content.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.input})
        messages.append({"role": "assistant", "content": content})

        for tc in response.tool_calls:
            result = tools.execute(tc.name, tc.input)
            messages.append({
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": tc.id, "content": result.message}],
            })

        response = provider.send_tool_result(messages=messages, system=system, tools=tool_schemas)
    else:
        # Schleife durch Iterationslimit beendet (kein break, also NICHT
        # ueber "kein Tool-Call mehr") - response ist die letzte
        # send_tool_result-Antwort, die selbst wieder Tool-Calls anfordern
        # kann und deren .text dann leer/nichtssagend waere. Ohne diesen
        # Fallback wuerde der Aufrufer einen leeren Text bekommen und den
        # Fehlschlag faelschlich fuer eine leere, aber gueltige Antwort
        # halten statt fuer einen abgebrochenen Tool-Call-Zyklus.
        if response.tool_calls:
            return (
                f"Konnte die Anfrage nicht abschließen: Iterationslimit "
                f"({max_iterations}) für Tool-Aufrufe erreicht, ohne eine "
                f"endgültige Antwort zu liefern."
            )

    return response.text.strip()


class PoolWorker:
    """Fuehrt einen einzelnen Agenten-Slot im Pool aus."""

    def __init__(
        self,
        agent_spec: PoolAgentSpec,
        config: "TarnoConfig",
        provider: "LLMProvider | None" = None,
    ) -> None:
        self.agent_spec = agent_spec
        self._config = config
        self._provider = provider or create_provider(
            config, provider_name=agent_spec.provider, model=agent_spec.model
        )

    @property
    def provider(self) -> "LLMProvider":
        """Der zugrundeliegende LLMProvider - fuer Orchestrator-eigene
        Aufrufe (Decompose/Merge), die nicht ueber run_subtask laufen."""
        return self._provider

    async def run_subtask(
        self,
        subtask: SubTask,
        context: list[PoolMessage],
        *,
        executor: Executor | None = None,
        workspace: dict[str, Any] | None = None,
    ) -> PoolMessage:
        """Bearbeitet einen zugewiesenen Teilschritt und liefert einen
        PoolMessage(kind="report") an den Lead zurueck. Wirft nie - Fehler
        werden als Text im Bericht mitgeteilt, damit ein einzelner
        fehlgeschlagener Worker nicht den ganzen Pool-Lauf abbricht.

        Wenn ein Workspace uebergeben wird, bekommt der Worker zusaetzlich
        read-only Tools (read_file/list_directory) und darf sie in einer
        kurzen, iterationsbegrenzten Schleife nutzen, um Code/Struktur selbst
        nachzuschlagen, statt nur deren Fehlen zu melden."""
        prompt = self._build_prompt(subtask, context, workspace)
        loop = asyncio.get_running_loop()
        started = time.monotonic()
        max_iterations = (
            self._config.coding.pool_worker_max_tool_iterations if self._config else 1
        )
        try:
            text = await loop.run_in_executor(
                executor,
                run_with_tool_loop,
                self._provider, prompt, WORKER_SYSTEM_PROMPT, workspace, max_iterations,
            )
        except Exception as exc:
            log.exception(
                "[Pool] Worker '%s' fehlgeschlagen bei Subtask %s", self.agent_spec.slug, subtask.id
            )
            text = f"Fehler bei der Bearbeitung: {exc}"

        elapsed = time.monotonic() - started
        log.debug(
            "[Pool] Worker '%s' Subtask %s in %.1fs abgeschlossen",
            self.agent_spec.slug, subtask.id, elapsed,
        )

        return PoolMessage(
            from_agent=self.agent_spec.slug,
            to_agent="lead",
            kind="report",
            text=text,
            timestamp_ms=int(time.time() * 1000),
            sub_task_id=subtask.id,
        )

    @staticmethod
    def _build_prompt(
        subtask: SubTask, context: list[PoolMessage], workspace: dict[str, Any] | None = None,
    ) -> str:
        parts = []
        label = workspace_label(workspace)
        if label:
            parts.append(label)
        parts.append(f"Deine zugewiesene Teilaufgabe:\n{subtask.description}")
        if context:
            context_lines = "\n".join(
                f"[{m.from_agent} -> {m.to_agent}] {m.text}" for m in context
            )
            parts.append(f"Bisheriger Kontext aus dem Pool:\n{context_lines}")
        return "\n\n".join(parts)
