# Planning Checklist

Use this for every non-trivial TARNO change.

## 1. Understand
- [ ] What is the user really trying to achieve?
- [ ] Which layer(s) are involved?
- [ ] Which launch mode(s) are involved? (PySide6, console, OVOS, gRPC/WinUI)
- [ ] Is the request ambiguous? Ask one focused clarification if yes.

## 2. Research
- [ ] Read the main source file(s) for the affected component.
- [ ] Read `tarno/core/config.py` and `config/default.yaml` if settings change.
- [ ] Read the existing UI or gRPC code for the feature if the change is visible.
- [ ] Search for call sites and event subscribers.
- [ ] Read any `Tarno Plans/` documents that apply.

## 3. Decide
- [ ] State the goal in one sentence.
- [ ] State the root cause (for bugs) with exact line numbers.
- [ ] Describe the chosen approach and why.
- [ ] List at least one rejected alternative and why.
- [ ] List affected files and components.
- [ ] Define verification steps.
- [ ] Identify risks (threading, audio, gRPC, packaging).
- [ ] Wait for user confirmation before implementing, unless trivial.

## 4. Implement
- [ ] One logical change at a time.
- [ ] Minimal diff; no unrelated refactoring.
- [ ] Imports at the top of the file.
- [ ] Thread-safe for `pygame`, `pyaudio`, `synthesizer`.
- [ ] gRPC proto/stubs/client/server kept in sync.
- [ ] WinUI XAML binding and `MainViewModel` updated together.
- [ ] Compile after each step:
  - `py -3.12 -m py_compile <file>`
  - `dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64`

## 5. Verify
- [ ] Runtime-tested for 15-30 seconds.
- [ ] Logs clean (no new warnings/errors).
- [ ] Existing behavior not broken.
- [ ] `pyinstaller` build still works if Python code changed.
- [ ] WinUI still builds if XAML/C# changed.
- [ ] New resources added to `tarno.spec` or `TARNO.UI.csproj`.

## 6. Review
- [ ] Summarize what changed.
- [ ] List modified files.
- [ ] Provide copy-pastable verification command.
- [ ] Update todo list.
- [ ] Use German for UI/log strings, English for code identifiers.
