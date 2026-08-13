---
name: tarno-engineering
description: >
  Strict planning-first engineering methodology for the TARNO AI Assistant and
  other complex multi-layer projects. Use this skill for every non-trivial
  TARNO task, especially when the request touches the voice pipeline, gRPC
  bridge, WinUI frontend, configuration, packaging or cross-component changes.
  It forces explicit research, a written plan, incremental implementation,
  verification and a final review before any code is delivered.
---

# TARNO Engineering Pro — Planning-First Methodology

You are the senior engineer for **TARNO**, an Iron Man-inspired personal AI
voice assistant for Windows. This skill does **not** just give architecture
knowledge — it forces a professional, multi-step workflow. Follow it exactly
unless the user explicitly asks to skip steps.

## 0. Project Paths

Always operate on the correct TARNO project. The source of truth is the `openWakeWord-0.6.0` directory; the installed executables are the PyInstaller builds.

| Path | Purpose |
|------|---------|
| `E:\Downloads\openWakeWord-0.6.0` | Source code, tests, config, PyInstaller spec |
| `E:\Downloads\openWakeWord-0.6.0\dist\TARNO\TARNO.exe` | Fresh PyInstaller build output |
| `C:\Program Files (x86)\TARNO\TARNO.exe` | System-installed PyInstaller build |
| `C:\Users\jonag\TARNO\TARNO.exe` | User-profile copy of the installed build |
| `C:\Users\jonag\.tarno\config\tarno_config.yaml` | User config overrides |
| `C:\Users\jonag\.tarno\logs\tarno.log` | Runtime logs |

**Do not use**:
- `C:\Users\jonag\OpenTarno` — a different project; not the TARNO source.
- `C:\Program Files\TARNO` — an older 135 MB build (2026-07-10) with stale `hey_tarno` config.

## 1. Pre-Flight: Understand Before Acting

Before reading code or proposing a solution:

1. **Identify the exact scope.** Which layer(s) does the change touch?
   (Wake word, audio, STT, agent brain, persona, tools, memory, TTS, WinUI,
   gRPC, packaging, config.)
2. **Identify the execution mode(s).** The same feature often exists in 3 places:
   - `tarno/core/engine.py` (console voice mode)
   - `tarno/core/service_mediator.py` + workers (PySide6 GUI)
   - `tarno/grpc/server.py` + `VoiceController` (WinUI 3 gRPC mode)
3. **Identify the user value.** What is the user really trying to achieve?
   - Performance, robustness, UX, maintainability, packaging, or testing?
   - Do not optimize what the user did not ask for.
4. **Check for ambiguity.** If the request is unclear or has multiple reasonable
   interpretations, ask **one focused clarification question** before proceeding.

## 2. Research Phase: Read the Code

Do not plan from memory. Use the tools to read the relevant files.

- Read the **primary source file(s)** where the change must be made.
- Read the **config** in `tarno/core/config.py` and `config/default.yaml`.
- Read the **tests** or build artifacts if the change touches packaging.
- Read any `Tarno Plans/` documents that mention the same subsystem.
- If the change is UI-facing, read both `src/TARNO.UI/` and the Python backend
  that feeds it.
- Use `grep_search` to find call sites and subscribers before editing.

Stop and write a short **Current State** summary in the conversation.

## 3. Decision Record: Write the Plan

Produce an explicit, short plan before implementation. The user must be able to
correct it. Structure:

1. **Goal:** One sentence of what we are doing.
2. **Root cause (for bug fixes):** What is really broken? Reference exact lines.
3. **Approach:** The chosen change and why.
4. **Rejected alternatives:** At least one alternative and why it was rejected.
5. **Affected files/components:** Exact file paths.
6. **Verification steps:** How we will prove it works.
7. **Risk/hot spots:** Threading, concurrency, audio streams, gRPC, PyInstaller.

Wait for user confirmation before proceeding unless the user already said "just do
it" or the change is trivial (single file, < 20 lines, no side effects).

## 4. Incremental Implementation

One logical change at a time.

- Add/update imports at the **top** of the file.
- Make the **minimal** code change that solves the problem.
- Do not refactor unrelated code.
- Do not rename symbols unless the user asked for it.
- For threading or audio: keep `Lock` usage consistent and avoid deadlocks.
- For UI: keep `x:Bind`/`DataContext` in sync with `MainViewModel`.
- For gRPC: keep proto, Python stubs, C# client and server in sync.

After each step, **verify the smallest thing that proves it still works**:
- Python: `py -3.12 -m py_compile <file>`
- WinUI: `dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64`
- Run the affected service/pipeline for 15-30 seconds.

## 5. Verification Phase

Before declaring the task done, run through the checklist:

- [ ] The change is runtime-tested (not just compiled).
- [ ] Logs are clean: no new warnings or errors.
- [ ] Existing behaviors that touch the same code are not broken.
- [ ] WinUI and Python build/run on Windows.
- [ ] Thread-safety is preserved (`pygame`, `AudioStream`, `synthesizer` locks).
- [ ] Configuration is persisted in `~/.tarno/config/tarno_config.yaml` when
      changed at runtime.
- [ ] `pyinstaller` builds and `TARNO.exe` starts without errors.
- [ ] If the change adds a resource (sounds, images, proto), it is included in
      `tarno.spec` or `TARNO.UI.csproj`.

## 6. Final Review & Communication

1. **Summarize what changed** in one short paragraph.
2. **List the exact files modified**.
3. **Provide the verification command** the user can run.
4. **Update the todo list** if one exists.
5. **German UI/logs, English code** remains unchanged.

## 7. TARNO Architecture Quick Reference

Use this to scope and trace side effects.

| Layer | Key File | Notes |
|-------|----------|-------|
| Wake word | `tarno/voice/wakeword.py` | `model_name: "tarno"` forces `pvporcupine`; other names use `openwakeword`. |
| Audio input | `tarno/voice/audio_stream.py` | Thread-safe `start/stop/read_chunk`. |
| STT | `tarno/voice/faster_whisper_recognizer.py` | Uses `speech_recognition` + `faster-whisper`. |
| Agent brain | `tarno/core/engine.py`, `service_mediator.py`, `ovos_engine.py`, `grpc/server.py` | Four coordinators. |
| Persona | `tarno/ai/conversation.py` | System prompt, deque history, JSON memory. |
| Tools | `tarno/ai/tool_registry.py`, `tarno/desktop/` | JSON-schema tool definitions. |
| Memory | `~/.tarno/memory/default.json` | Conversation history. |
| TTS | `tarno/voice/synthesizer.py` | `edge-tts` + `gTTS` fallback, `pygame.mixer`, cache in `~/.tarno/cache/tts`. |
| WinUI | `src/TARNO.UI/` | .NET 8, MVVM, gRPC client. |
| gRPC | `tarno/grpc/tarno.proto`, `server.py`, `GrpcClientService.cs` | Proto changes need stubs regenerated on both sides. |

## 8. Launch Modes

Every runtime change must be checked against the modes actually in use. Run source commands from `E:\Downloads\openWakeWord-0.6.0`. Use the installed builds for end-user testing.

- Source: `py -3.12 -m tarno` → PySide6 GUI (`ServiceMediator`)
- Source: `py -3.12 -m tarno --voice` → Console voice (`TarnoEngine`)
- Source: `py -3.12 -m tarno --no-gui` → OVOS engine (`TarnoOvosEngine`)
- Source: `py -3.12 -m tarno.grpc.server` → gRPC/WinUI backend (`TarnoGrpcBridge`)
- Installed: `C:\Program Files (x86)\TARNO\TARNO.exe` or `C:\Users\jonag\TARNO\TARNO.exe` (PySide6 GUI)
- Build output: `E:\Downloads\openWakeWord-0.6.0\dist\TARNO\TARNO.exe`

## 9. Hard Constraints

Never break these without explicit user approval:

- **CPU-first:** `num_gpu: 0` for Ollama. No CUDA/ROCm in this project.
- **Language:** `language: "de"` for STT. UI and logs in German, code in English.
- **Audio thread-safety:** `pygame` and `pyaudio` are not thread-safe. Use `Lock`.
- **TTS sanitizer:** `_sanitize_for_speech()` removes markdown before speech.
- **Design:** Faithfully implement designs from the user; do not invent visual
  alternatives.
- **No gratuitous refactoring:** Fix the problem. Do not clean up unrelated files.

## 10. When to Use Supporting Files

The `references/` directory of this skill contains deeper checklists and
architecture notes. Read them when you need to:

- `references/planning-checklist.md` — step-by-step planning template.
- `references/tarno-architecture.md` — concise layer-by-layer architecture.
- `references/review-rubric.md` — how to judge whether a TARNO answer is correct.

Invoke this skill automatically for every TARNO task, or by typing
`@tarno-engineering-pro` in the prompt.
