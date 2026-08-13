# Review Rubric for TARNO Answers

Use this to judge whether a plan or implementation is good enough to deliver.

## Correctness
- [ ] The backend/frontend used by the request is correctly identified.
- [ ] The active launch mode is respected (PySide6, console, OVOS, gRPC).
- [ ] Config values are read from `config/default.yaml` and the actual runtime
      `TarnoConfig` object, not assumed.
- [ ] Line numbers and file paths cited are correct.

## Completeness
- [ ] All files that need to change are listed.
- [ ] For UI changes: both XAML and ViewModel/code-behind are covered.
- [ ] For gRPC changes: proto, Python stubs, C# client, and server are covered.
- [ ] For packaging changes: `tarno.spec`, PyInstaller, and NSIS installer are
      covered.
- [ ] Verification steps are concrete and executable.

## Side Effects
- [ ] The voice pipeline is traced end-to-end before changes.
- [ ] Thread-safety is considered for `pygame`, `pyaudio`, and `synthesizer`.
- [ ] Audio stream lifecycle (`start`/`stop`/`read_chunk`) is not broken.
- [ ] Existing settings and cached data are not accidentally overwritten.

## Minimalism
- [ ] The diff is the smallest change that solves the problem.
- [ ] No unrelated refactoring or renaming.
- [ ] No new dependencies unless required.

## Communication
- [ ] Reasoning is shown before implementation.
- [ ] Affected files and verification commands are listed.
- [ ] German UI/log strings, English code identifiers.
- [ ] Status is summarized at the end.

## Red Flags
- [ ] Citing a file that does not exist (e.g., `tarno/grpc/server.py` before it
      was created, or `tarno/gui/` for new features — the PySide6 GUI is
      frozen).
- [ ] Recommending a config change that is ignored at runtime due to a hardcoded
      override (e.g., `porcupine` forcing `patience = 1`).
- [ ] Using `pygame.mixer.music` for a short confirmation sound that should
      overlap with TTS.
- [ ] Forgetting `threading.Lock` around `pygame` operations.
- [ ] Proposing a WinUI-only solution when the user uses the console or gRPC
      mode.
