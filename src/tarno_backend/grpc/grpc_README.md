# `tarno_backend/grpc/` — bridge to the WinUI 3 frontend

The gRPC server that exposes the Python backend (`tarno_backend/core/engine.py`) to
the C# WinUI frontend at `src/TARNO.UI/`. This is the primary integration
point between the two halves of TARNO.

## Files

- **`server.py`**: the real gRPC server — wraps `TarnoEngine`, streams
  chat/voice/system-info updates to the UI, handles permission round-trips
  (`PermissionDialog`, see TD-025), settings, and API-key management via
  `SecretsVault`. Binds to loopback only (`127.0.0.1` / `[::1]`), not a
  wildcard address (TD-018 — this used to be a local-network security hole).
- **`mock_engine.py`**: a fake engine for developing/testing the WinUI
  frontend without real API keys or a working voice pipeline. Launched via
  `python -m tarno_backend.grpc --mock` (with `src/` on `PYTHONPATH`).
- **`__main__.py`**: entry point (`python -m tarno_backend.grpc [--mock] [--port 50051]`).
- **`tarno.proto`**: the protobuf service/message definitions — the actual
  source of truth for the wire protocol.
- **`tarno_pb2.py`** / **`tarno_pb2_grpc.py`**: generated from `tarno.proto`.
  **Do not edit by hand** — regenerate via `grpcio-tools` (see
  `requirements-dev.txt`) whenever `tarno.proto` changes.

## Cross-references

- C# client side: `src/TARNO.UI/Services/GrpcClientService.cs` (auto-reconnect with backoff, TD-003)
- Engine being wrapped: `tarno_backend/core/engine.py` (see `core_README.md`)
- Security history: [`workspace/debug/docs/technical-debt-catalog.md`](../../../workspace/debug/docs/technical-debt-catalog.md) (TD-003, TD-018, TD-025)
