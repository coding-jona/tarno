# TARNO

A personal, voice-first AI assistant for Windows. Local-first and CPU-only
where it matters (wake word, speech recognition, memory embeddings), with
pluggable cloud LLM providers for the actual conversation. German UI/voice
persona, English code.

> **Status:** actively developed, not a finished product. Known gaps and
> in-progress work are tracked openly in
> [`workspace/debug/docs/technical-debt-catalog.md`](workspace/debug/docs/docs_README.md)
> rather than hidden — check there before assuming something is broken vs.
> deliberately unfinished.

## What it does

- **Voice pipeline**: wake-word detection (openWakeWord / Vosk / Porcupine)
  → speech-to-text (faster-whisper / Vosk) → LLM → text-to-speech (Piper,
  local CPU synthesis, with edge-tts as a network fallback).
- **Multiple LLM providers**: Mistral, Claude, Gemini, Groq, Hugging Face,
  Ollama (fully local/offline), plus a generic OpenAI-compatible fallback —
  switchable at runtime, with an automatic fallback chain.
- **Tool use / autonomy**: a native coding-agent backend, a multi-agent
  "pool" mode for parallel collaboration on coding tasks, autonomous
  proactive briefings, reminders, and routines with human-in-the-loop
  confirmation for anything risky.
- **Long-term memory**: local SQLite + on-device embeddings for semantic
  recall of facts and preferences — no external service.
- **Integrations**: Discord push-to-talk, Git, calendar/email, smart home,
  Minecraft voice chat, and a "Dynamic Hybrid Mesh" that lets TARNO run
  across multiple devices (this PC, a phone, an ESP32 scanner).
- **Vision** (optional): local motion-gated webcam capture with autonomous
  reactions via the Mistral Vision API.
- **Security by default**: OS-keyring-backed secret storage, PII redaction
  in logs, encrypted-at-rest sensitive data, and a build-time secret-leak
  scanner.

## Architecture

```
src/tarno_backend/   Python backend (import name: tarno_backend)
src/TARNO.UI/        WinUI 3 frontend (C#) — the active, production UI
                      ↕ gRPC
```

The two halves talk exclusively over gRPC (`tarno_backend/grpc/`). Two
older Python-based UI stacks (`tarno_backend/ui/`, `tarno_backend/gui/`)
still exist in the tree but are deprecated in favor of `src/TARNO.UI/` —
see their READMEs for why they're kept around.

`TarnoEngine` (`tarno_backend/core/engine.py`) is the execution layer
everything else plugs into. Autonomous/cognitive features (proactive
briefings, task planning, extensions) are built as separate layers on top
of it, not folded into it — see
[`CLAUDE.md`](CLAUDE.md) for the project's standing architectural rules.

Every subpackage under `src/tarno_backend/` and `src/TARNO.UI/` has its own
`README.md` / `<name>_README.md` with a file-by-file breakdown and
cross-references — start at
[`src/tarno_backend/core/core_README.md`](src/tarno_backend/core/core_README.md)
or [`src/TARNO.UI/README.md`](src/TARNO.UI/README.md) if you want to go
deeper than this overview.

## Repository layout

```
src/tarno_backend/   Python backend source
src/TARNO.UI/         WinUI 3 frontend source
config/               Runtime configuration (persona, OVOS config)
workspace/            Everything non-shipped: tests, docs, plans, build
                       scripts, parked ideas — see its own README
.github/workflows/    CI (Windows-only test matrix) and the release
                       installer pipeline
```

See [`workspace/workspace_README.md`](workspace/workspace_README.md) for
the full breakdown of what lives under `workspace/` and why it's kept
separate from `src/`.

## Getting started

**Requirements:** Python 3.11 or 3.12, .NET 8 SDK (for the frontend),
Windows (the backend has Windows-specific integrations — see
`requirements.txt`'s "System / Windows integration" section — and the
frontend is WinUI 3, which is Windows-only).

```powershell
# Backend dependencies
pip install -r requirements-dev.txt   # includes requirements.txt + test tooling

# Run the backend (from repo root)
$env:PYTHONPATH = "src"; py -3.12 -m tarno_backend.grpc

# Build the frontend
dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64
```

API keys for LLM providers are never entered into the app directly — see
[`workspace/debug/docs/api-keys.md`](workspace/debug/docs/docs_README.md)
for how they're configured, or use the first-start setup wizard.

## Testing

```powershell
# Everything (build + tests), handles PYTHONPATH itself
workspace/scripts/verify.ps1

# Just the Python test suite
pytest workspace/debug/tests
```

CI (`.github/workflows/ci.yml`) runs the same `pytest` suite on
`windows-latest` for Python 3.11 and 3.12 — see
[`workspace/debug/tests/tests_README.md`](workspace/debug/tests/tests_README.md)
for conventions, including how tests that need optional/legacy
dependencies (OVOS, the deprecated PySide6 UI, `pynput`) skip themselves
cleanly instead of requiring those packages in CI.

## Documentation map

- [`CLAUDE.md`](CLAUDE.md) — standing architecture rules and constraints
  for anyone (human or AI) working on this codebase.
- [`workspace/debug/docs/adr/`](workspace/debug/docs/adr/adr_README.md) —
  Architecture Decision Records: why things are built the way they are.
- [`workspace/debug/docs/technical-debt-catalog.md`](workspace/debug/docs/docs_README.md) —
  known issues, resolved and open, with reasoning.
- [`workspace/plans/`](workspace/plans/plans_README.md) — planning
  documents and specs (earlier-stage than ADRs, some historical).

## License

Not yet decided — treat this as source-available for now, not open source
under any specific terms, until a `LICENSE` file is added.
