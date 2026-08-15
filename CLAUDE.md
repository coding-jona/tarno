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

- Python backend: src/tarno_backend/ (import name `tarno_backend`, needs `src/` on PYTHONPATH)
- WinUI 3 frontend: src/TARNO.UI/
- Communication: gRPC

Core execution:
- TarnoEngine = execution layer.
- Cognitive features must be implemented as separate layers.
- Do not replace TarnoEngine without explicit approval.

## Important Paths

- src/tarno_backend/core: engine, config, services (see core_README.md there)
- src/tarno_backend/ai: LLM providers and tools (see ai_README.md there)
- src/tarno_backend/voice: audio pipeline (see voice_README.md there)
- src/TARNO.UI: Windows frontend
- workspace/installer: the live Windows build (build.ps1, Tarno Mesh.spec,
  setup.iss/Inno Setup, build_installer.py, requirements*.txt, FreeBSD
  build notes) - two levels below repo root, so its scripts resolve the
  repo root as `../..`.
- workspace/debug/{tests,docs,installer,tools}: everything non-shipped
  (test suite, ADRs/docs, debug scripts). NOTE: workspace/debug/installer/
  is a DIFFERENT, dead directory - leftover NSIS scaffolding
  (version.nsh only) from a superseded packaging approach, not to be
  confused with workspace/installer/ above.
- workspace/plans, workspace/scripts, workspace/future: planning docs, build scripts, parked ideas

## Technical Constraints

- CPU-first Ollama configuration.
- No CUDA/ROCm assumptions.
- Use dataclasses and type hints.
- Use logging, not print.
- Follow existing async/threading patterns.

## Build

Backend (PowerShell, from repo root):
$env:PYTHONPATH = "src"; py -3.12 -m tarno_backend.grpc

Frontend:
dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64

Full verify (build + tests, handles PYTHONPATH itself):
workspace/scripts/verify.ps1