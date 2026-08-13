"""End-to-end gRPC streaming tests for the Agent-Pool backend (Phase 3)."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from tarno_backend.ai.coding.agent import CodingAgent
from tarno_backend.ai.coding.protocol import CodingOutput
from tarno_backend.ai.pool.models import PoolMessage
from tarno_backend.core.config import TarnoConfig
from tarno_backend.core.exceptions import PermissionDeniedError
from tarno_backend.grpc import tarno_pb2
from tarno_backend.grpc.mock_engine import MockTarnoEngine
from tarno_backend.grpc.server import TarnoGrpcBridge


class _FakeOrchestrator:
    """Deterministic PoolOrchestrator stand-in for gRPC streaming tests."""

    def __init__(self, config, pool_config) -> None:
        self.pool_config = pool_config

    def close(self) -> None:
        pass

    async def run(self, prompt, fnames, on_message=None, workspace=None) -> PoolMessage:
        lead_slug = self.pool_config.lead.slug
        worker_slug = self.pool_config.workers[0].slug
        if on_message:
            on_message(PoolMessage(from_agent=lead_slug, to_agent=worker_slug, kind="assign", text="Bearbeite X"))
            on_message(PoolMessage(from_agent=worker_slug, to_agent="lead", kind="report", text="Erledigt X"))
        final = PoolMessage(from_agent=lead_slug, to_agent="broadcast", kind="merge_decision", text="Finale Anweisung")
        if on_message:
            on_message(final)
        return final


class _EngineWithCoding(MockTarnoEngine):
    def __init__(self, config: TarnoConfig) -> None:
        super().__init__(config)
        self._coding_agent = CodingAgent(config, event_bus=self.event_bus, get_workspace=lambda: None)


class PoolGrpcTests(unittest.TestCase):
    def test_pool_task_streams_messages_and_final_response(self) -> None:
        async def _run() -> None:
            config = TarnoConfig()
            engine = _EngineWithCoding(config)
            bridge = TarnoGrpcBridge(engine)
            try:
                loop = asyncio.get_running_loop()
                bridge._loop = loop
                conn = bridge.add_client()

                fake_outputs = [CodingOutput(kind="summary", text="Pool-Änderung angewendet.")]
                with patch("tarno_backend.grpc.server.PoolOrchestrator", _FakeOrchestrator), \
                     patch("tarno_backend.grpc.server.apply_merged_instruction", return_value=iter(fake_outputs)):
                    request = tarno_pb2.StartPoolTaskRequest(
                        prompt="Docstrings ergänzen",
                        workspace=tarno_pb2.Workspace(id="ws", name="ws", root_path="/tmp/x"),
                        file_paths=[],
                        agents=[
                            tarno_pb2.PoolAgentSpecProto(provider="mistral", model="m1", is_lead=True),
                            tarno_pb2.PoolAgentSpecProto(provider="claude", model="m2", is_lead=False),
                        ],
                        chat_id="c1",
                        read_only=True,
                    )
                    bridge.handle_start_pool_task(request)

                    received: list[tarno_pb2.ServerMessage] = []
                    for _ in range(10):
                        msg = await asyncio.wait_for(conn.queue.get(), timeout=3.0)
                        received.append(msg)
                        if msg.HasField("pool_task_response"):
                            break

                pool_messages = [m.pool_message for m in received if m.HasField("pool_message")]
                self.assertEqual(len(pool_messages), 3)
                self.assertEqual(pool_messages[0].kind, "assign")
                self.assertEqual(pool_messages[1].kind, "report")
                self.assertEqual(pool_messages[2].kind, "merge_decision")
                self.assertTrue(all(m.chat_id == "c1" for m in pool_messages))

                response = [m.pool_task_response for m in received if m.HasField("pool_task_response")]
                self.assertEqual(len(response), 1)
                self.assertTrue(response[0].success)
                self.assertEqual(response[0].summary, "Finale Anweisung")
                self.assertEqual(response[0].chat_id, "c1")
            finally:
                bridge.shutdown()

        asyncio.run(_run())

    def test_permission_denial_blocks_edit_and_reports_failure(self) -> None:
        """Kontext-Effizienz-Plan Phase 5: genau ein request_coding_edit-
        Aufruf am Merge-Schritt - lehnt der Nutzer ab, wird apply_merged_
        instruction NIE aufgerufen und der Pool-Lauf meldet Fehlschlag."""
        async def _run() -> None:
            config = TarnoConfig()
            engine = _EngineWithCoding(config)

            class _DenyingPermissionService:
                def request_coding_edit(self, prompt, auto_allow=False):
                    raise PermissionDeniedError("Nutzer hat abgelehnt")

            engine._coding_agent._permission_service = _DenyingPermissionService()
            bridge = TarnoGrpcBridge(engine)
            try:
                loop = asyncio.get_running_loop()
                bridge._loop = loop
                conn = bridge.add_client()

                with patch("tarno_backend.grpc.server.PoolOrchestrator", _FakeOrchestrator), \
                     patch("tarno_backend.grpc.server.apply_merged_instruction") as mock_apply:
                    request = tarno_pb2.StartPoolTaskRequest(
                        prompt="Ändere etwas",
                        workspace=tarno_pb2.Workspace(id="ws", name="ws", root_path="/tmp/x"),
                        agents=[
                            tarno_pb2.PoolAgentSpecProto(provider="mistral", model="m1", is_lead=True),
                            tarno_pb2.PoolAgentSpecProto(provider="claude", model="m2", is_lead=False),
                        ],
                        chat_id="c3",
                        read_only=False,
                    )
                    bridge.handle_start_pool_task(request)

                    received: list[tarno_pb2.ServerMessage] = []
                    for _ in range(10):
                        msg = await asyncio.wait_for(conn.queue.get(), timeout=3.0)
                        received.append(msg)
                        if msg.HasField("pool_task_response"):
                            break

                mock_apply.assert_not_called()
                response = [m.pool_task_response for m in received if m.HasField("pool_task_response")]
                self.assertEqual(len(response), 1)
                self.assertFalse(response[0].success)
                self.assertIn("abgelehnt", response[0].error)
            finally:
                bridge.shutdown()

        asyncio.run(_run())

    def test_invalid_agent_count_rejected_without_running_orchestrator(self) -> None:
        async def _run() -> None:
            config = TarnoConfig()
            engine = _EngineWithCoding(config)
            bridge = TarnoGrpcBridge(engine)
            try:
                loop = asyncio.get_running_loop()
                bridge._loop = loop
                conn = bridge.add_client()

                request = tarno_pb2.StartPoolTaskRequest(
                    prompt="X",
                    workspace=tarno_pb2.Workspace(id="ws", name="ws", root_path="/tmp/x"),
                    agents=[tarno_pb2.PoolAgentSpecProto(provider="mistral", model="m1", is_lead=True)],
                    chat_id="c1",
                )
                bridge.handle_start_pool_task(request)

                msg = await asyncio.wait_for(conn.queue.get(), timeout=3.0)
                self.assertTrue(msg.HasField("pool_task_response"))
                self.assertFalse(msg.pool_task_response.success)
                self.assertIn("2", msg.pool_task_response.error)
            finally:
                bridge.shutdown()

        asyncio.run(_run())

    def test_coding_task_still_works_independently_of_pool_executor(self) -> None:
        """Executor isolation: a normal single-agent coding task must not
        be affected by the pool executor's existence."""
        async def _run() -> None:
            config = TarnoConfig()
            config.command_execution.autonomy_mode = "ultimate"
            engine = _EngineWithCoding(config)
            outputs = [CodingOutput(kind="summary", text="Einzel-Agent fertig")]
            engine._coding_agent.dispatcher.get_backend = lambda *_a, **_kw: _FakeBackendForCoding(outputs)
            bridge = TarnoGrpcBridge(engine)
            try:
                loop = asyncio.get_running_loop()
                bridge._loop = loop
                conn = bridge.add_client()

                import os
                import tempfile
                with tempfile.TemporaryDirectory() as tmp:
                    os.makedirs(os.path.join(tmp, ".git"))
                    request = tarno_pb2.CodingTaskRequest(
                        prompt="refactor",
                        workspace=tarno_pb2.Workspace(id="ws", name="ws", root_path=tmp),
                        file_paths=[],
                        read_only=True,
                        chat_id="c2",
                    )
                    bridge.handle_coding_task(request)

                    msg = await asyncio.wait_for(conn.queue.get(), timeout=3.0)
                    self.assertTrue(msg.HasField("coding_output"))
                    self.assertEqual(msg.coding_output.text, "Einzel-Agent fertig")
            finally:
                bridge.shutdown()

        asyncio.run(_run())


class _FakeBackendForCoding:
    def __init__(self, outputs) -> None:
        self.outputs = outputs

    def run(self, prompt, workspace, fnames, read_only, on_output=None):
        for output in self.outputs:
            yield output


if __name__ == "__main__":
    unittest.main()
