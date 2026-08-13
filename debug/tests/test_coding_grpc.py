"""End-to-end gRPC streaming tests for the coding backend."""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from typing import Any, Iterator

from tarno.ai.coding.agent import CodingAgent
from tarno.ai.coding.protocol import CodingOutput
from tarno.core.config import TarnoConfig
from tarno.grpc import tarno_pb2
from tarno.grpc.mock_engine import MockTarnoEngine
from tarno.grpc.server import TarnoGrpcBridge


class _FakeBackend:
    """Deterministic coding backend for gRPC streaming tests."""

    def __init__(self, outputs: list[CodingOutput]) -> None:
        self.outputs = outputs

    def run(
        self,
        prompt: str,
        workspace: dict[str, Any],
        fnames: list[str],
        read_only: bool,
        on_output: Any | None = None,
    ) -> Iterator[CodingOutput]:
        for output in self.outputs:
            yield output


class _EngineWithCoding(MockTarnoEngine):
    """Mock engine that exposes a real CodingAgent with a fake backend."""

    def __init__(self, config: TarnoConfig, outputs: list[CodingOutput]) -> None:
        super().__init__(config)
        self._coding_agent = CodingAgent(
            config,
            event_bus=self.event_bus,
            get_workspace=lambda: None,
        )
        self._coding_agent.dispatcher.get_backend = lambda *_a, **_kw: _FakeBackend(outputs)


class CodingGrpcTests(unittest.TestCase):
    def test_coding_task_streams_output(self) -> None:
        async def _run() -> None:
            config = TarnoConfig()
            config.command_execution.autonomy_mode = "ultimate"

            outputs = [
                CodingOutput(kind="text", text="Erste Zeile"),
                CodingOutput(kind="text", text="Zweite Zeile"),
                CodingOutput(kind="summary", text="Fertig"),
            ]
            engine = _EngineWithCoding(config, outputs)
            bridge = TarnoGrpcBridge(engine)
            try:
                loop = asyncio.get_running_loop()
                bridge._loop = loop
                conn = bridge.add_client()

                with tempfile.TemporaryDirectory() as tmp:
                    os.makedirs(os.path.join(tmp, ".git"))
                    request = tarno_pb2.CodingTaskRequest(
                        prompt="refactor",
                        workspace=tarno_pb2.Workspace(
                            id="ws",
                            name="ws",
                            root_path=tmp,
                            folders=[
                                tarno_pb2.WorkspaceFolder(id="f", name="f", path=tmp)
                            ],
                        ),
                        file_paths=[],
                        read_only=True,
                        chat_id="c1",
                    )
                    bridge.handle_coding_task(request)

                    received: list[tarno_pb2.ServerMessage] = []
                    for _ in range(10):
                        msg = await asyncio.wait_for(conn.queue.get(), timeout=3.0)
                        received.append(msg)
                        if len(received) >= 3:
                            break

                    coding = [
                        m for m in received if m.HasField("coding_output")
                    ]
                    self.assertEqual(len(coding), 3, f"Got messages: {received}")
                    self.assertEqual(coding[0].coding_output.kind, "text")
                    self.assertEqual(coding[0].coding_output.text, "Erste Zeile")
                    self.assertEqual(coding[0].coding_output.chat_id, "c1")
                    self.assertEqual(coding[2].coding_output.kind, "summary")
            finally:
                bridge.shutdown()

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
