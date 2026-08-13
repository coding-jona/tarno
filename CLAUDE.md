# TARNO AI Assistant

Personal AI agent for Windows.
German UI/persona, English code.

## Rules

- Use planning-first workflow for non-trivial tasks.
- Code identifiers in English.
- UI strings and logs in German.
- No unrelated refactoring.
- Preserve existing architecture unless explicitly approved.
- Verify changes with tests/build commands.
- Never expose API keys.

## Architecture

TARNO consists of:

- Python backend: tarno/
- WinUI 3 frontend: src/TARNO.UI/
- Communication: gRPC

Core execution:
- TarnoEngine = execution layer.
- Cognitive features must be implemented as separate layers.
- Do not replace TarnoEngine without explicit approval.

## Important Paths

- tarno/core: engine, config, services
- tarno/ai: LLM providers and tools
- tarno/voice: audio pipeline
- src/TARNO.UI: Windows frontend

## Technical Constraints

- CPU-first Ollama configuration.
- No CUDA/ROCm assumptions.
- Use dataclasses and type hints.
- Use logging, not print.
- Follow existing async/threading patterns.

## Build

Backend:
py -3.12 -m tarno.grpc

Frontend:
dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64