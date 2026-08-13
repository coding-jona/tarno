TARNO Architecture Reference

Quick map for tracing side effects across the TARNO stack.

This document is a reference for planning, review and implementation.
Do not modify architecture assumptions without checking existing plans and source code.

8 Layers
#	Layer	Purpose	Key File
1	Wake Word	Always-on "Tarno" detection	tarno/voice/wakeword.py
2	Audio	Microphone capture, 16 kHz mono PCM	tarno/voice/audio_stream.py
3	STT	Speech → Text conversion	tarno/voice/faster_whisper_recognizer.py
4	Agent Brain	Orchestration, reasoning and tools	tarno/core/engine.py, service_mediator.py, ovos_engine.py, grpc/server.py
5	Persona	System prompt, personality and conversation state	tarno/ai/conversation.py
6	Tools	Desktop automation and external actions	tarno/ai/tool_registry.py, tarno/desktop/
7	Memory	Conversation persistence and stored context	~/.tarno/memory/default.json
8	TTS	Text → Speech output	tarno/voice/synthesizer.py
Runtime Launch Modes

Every change must identify which runtime mode is affected.

Command	Mode	Coordinator	Frontend
py -3.12 -m tarno	PySide6 GUI	ServiceMediator + QWorkers	tarno/gui/
py -3.12 -m tarno --voice	Console voice mode	TarnoEngine	Terminal
py -3.12 -m tarno --no-gui	OVOS engine mode	TarnoOvosEngine	None
py -3.12 -m tarno.grpc.server	gRPC backend	TarnoGrpcBridge + VoiceController	src/TARNO.UI (WinUI 3)

A solution that only works for one launch mode must explicitly state why the other modes are unaffected.

Critical Cross-Cutting Concerns
Voice Pipeline

Voice-related changes must trace the complete path:

Wake Word
    ↓
Audio Stream
    ↓
STT
    ↓
Agent Brain
    ↓
Persona / LLM
    ↓
Tool Execution
    ↓
TTS

Changes normally need review in:

tarno/core/engine.py
tarno/core/service_mediator.py
tarno/grpc/server.py

Do not modify one pipeline entry point while ignoring other active execution paths.

Configuration Flow

Configuration follows this hierarchy:

config/default.yaml
        ↓
~/.tarno/config/tarno_config.yaml
        ↓
tarno_config.yaml (CWD)
        ↓
Environment variables (TARNO_*)

Configuration changes must verify:

tarno/core/config.py
config/default.yaml
runtime TarnoConfig object
persisted user configuration
WinUI MainViewModel if exposed to users

Never assume a YAML value is active without checking runtime loading.

gRPC Changes

gRPC changes require synchronization between:

tarno/grpc/tarno.proto
Python generated files:
tarno_pb2.py
tarno_pb2_grpc.py
Python server:
tarno/grpc/server.py
C# generated client:
TARNO.Grpc namespace
WinUI client:
src/TARNO.UI

A change on only one side is incomplete.

Packaging Changes

Packaging changes must consider:

tarno.spec
PyInstaller build
bundled resources
dist/TARNO
NSIS installer
TARNO_Installer_4.0.0.exe

A successful source run does not prove a packaged build works.

Configuration Defaults

Important current defaults:

language: "de"
STT and TTS language.
llm.provider: "mistral"
Default LLM provider.
wakeword.model_name: "tarno"
Uses the Tarno wake word configuration.
wakeword.confirm_wake_word: false
No spoken confirmation by default.
tts_engine: "edge-tts"
Default TTS engine.
voice: "de-DE-ConradNeural"
Default German voice.
ollama.num_gpu: 0
CPU-first execution.
Do not introduce CUDA/ROCm assumptions without explicit approval.
Engineering Constraints

The following constraints are considered architecture rules.

Audio Safety

Audio components are sensitive:

pygame
pyaudio
synthesizer

Thread safety must be preserved.

Never remove synchronization around audio operations without proving safety.

Minimal Changes

Preferred implementation style:

smallest possible diff
no unrelated refactoring
no dependency additions without necessity
no renaming without requirement

A working architecture is more important than cleanup.

Planning Requirement

Before implementation, every non-trivial change requires:

Identify affected layer(s).
Identify affected launch mode(s).
Read relevant source files.
Explain current state.
Provide implementation plan.
List risks.
Wait for confirmation unless explicitly instructed otherwise.
Review Reminder

When reviewing TARNO changes, check:

Is the correct backend identified?
Is the active launch mode respected?
Are all affected files listed?
Are side effects traced?
Are threading and audio risks considered?
Are verification steps executable?
Is existing behavior preserved?

The goal is not only to make code work, but to keep TARNO maintainable as a multi-layer AI assistant.