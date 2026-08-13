# TARNO Architecture Reference

Quick map for tracing side effects across the stack.

## 8 Layers

| # | Layer | Purpose | Key File |
|---|-------|---------|----------|
| 1 | Wake Word | Always-on "Tarno" detection | `tarno/voice/wakeword.py` |
| 2 | Audio | Microphone capture, 16 kHz mono PCM | `tarno/voice/audio_stream.py` |
| 3 | STT | Speech → Text | `tarno/voice/faster_whisper_recognizer.py` |
| 4 | Agent Brain | Orchestration + tools | `tarno/core/engine.py`, `service_mediator.py`, `ovos_engine.py`, `grpc/server.py` |
| 5 | Persona | Prompts + conversation history | `tarno/ai/conversation.py` |
| 6 | Tools | Desktop automation | `tarno/ai/tool_registry.py`, `tarno/desktop/` |
| 7 | Memory | Conversation persistence | `~/.tarno/memory/default.json` |
| 8 | TTS | Text → Speech | `tarno/voice/synthesizer.py` |

## 4 Launch Modes

| Command | Mode | Coordinator | Frontend |
|---------|------|-------------|----------|
| `py -3.12 -m tarno` | PySide6 GUI | `ServiceMediator` + QWorkers | `tarno/gui/` (purple) |
| `py -3.12 -m tarno --voice` | Console voice | `TarnoEngine` | Terminal |
| `py -3.12 -m tarno --no-gui` | OVOS engine | `TarnoOvosEngine` | None |
| `py -3.12 -m tarno.grpc.server` | gRPC backend | `TarnoGrpcBridge` + `VoiceController` | `src/TARNO.UI` (WinUI 3) |

## Critical Cross-Cutting Concerns

- **Voice pipeline changes** usually need to be mirrored in three places:
  `engine.py`, `service_mediator.py`/`voice_worker.py`, `grpc/server.py`.
- **Config changes** affect `tarno/core/config.py`, `config/default.yaml`, the
  YAML persistence in `~/.tarno/config/tarno_config.yaml`, and the WinUI
  `MainViewModel` if exposed in settings.
- **gRPC changes** require `tarno/grpc/tarno.proto`, Python stubs
  (`tarno_pb2.py`, `tarno_pb2_grpc.py`), and C# generated types
  (`TARNO.Grpc` namespace) to be regenerated.
- **PyInstaller changes** require updating `tarno.spec` and rebuilding both
  `dist/TARNO` and `TARNO_Installer_4.0.0.exe`.

## Configuration Hierarchy

Default: `config/default.yaml`  →  User: `~/.tarno/config/tarno_config.yaml`  →  CWD: `tarno_config.yaml`  →  Env vars (`TARNO_*`).

## Important Defaults

- `language: "de"` — STT and TTS language.
- `llm.provider: "mistral"` — default LLM.
- `wakeword.model_name: "tarno"` — forces `pvporcupine` backend.
- `wakeword.confirm_wake_word: false` — no spoken confirmation by default.
- `tts_engine: "edge-tts"` with voice `de-DE-ConradNeural`.
- `ollama.num_gpu: 0` — CPU-only on Windows/AMD.
