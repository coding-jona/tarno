# Planning Checklist

Use this for every non-trivial TARNO change.

Before using this checklist determine the current task type:

- [ ] Architecture Review
- [ ] Implementation Planning
- [ ] Implementation
- [ ] Verification

Do not use an implementation workflow for architecture review.

---

# Architecture Review Mode

Use this when reviewing TARNO plans or frozen architecture.

## Rules

- [ ] Read the original plan as reference only.
- [ ] Do not directly modify frozen architecture documents.
- [ ] Create separate findings instead.
- [ ] Separate problems from redesign suggestions.
- [ ] Preserve existing architecture decisions unless a critical issue exists.

## Review Questions

- [ ] Are component responsibilities clearly defined?
- [ ] Are ownership boundaries explicit?
- [ ] Are state transitions complete?
- [ ] Are concurrency assumptions documented?
- [ ] Are failure cases covered?
- [ ] Are shutdown and recovery behaviors defined?
- [ ] Are external dependencies realistic?

## Finding Format

Every finding should contain:

- Severity
- Location
- Problem
- Reason
- Recommendation

---

# 1. Understand

- [ ] What is the user really trying to achieve?
- [ ] Which layer(s) are involved?
- [ ] Which launch mode(s) are involved?
  - PySide6
  - Console
  - OVOS
  - gRPC/WinUI
- [ ] Is the request ambiguous?
- [ ] Ask one focused clarification if required.

---

# 2. Research

Before planning:

- [ ] Read the main source file(s) for the affected component.
- [ ] Read `tarno/core/config.py` and `config/default.yaml` if settings change.
- [ ] Read the existing UI or gRPC code for visible features.
- [ ] Search for call sites and event subscribers.
- [ ] Read applicable `Tarno Plans/` documents.
- [ ] Check tests and build files when packaging is involved.

Do not plan from memory.

After research provide:

## Current State Summary

Include:

- Existing behavior.
- Components involved.
- Dependencies.
- Risks.

---

# 3. Decide

Before implementation, create a decision record:

- [ ] State the goal in one sentence.
- [ ] State the root cause for bugs.
- [ ] Reference exact files and line numbers when possible.
- [ ] Describe the chosen approach.
- [ ] Explain why this approach was selected.
- [ ] List at least one rejected alternative.
- [ ] List affected files and components.
- [ ] Define verification steps.
- [ ] Identify risks:
  - threading
  - audio
  - gRPC
  - packaging
  - configuration

- [ ] Wait for user confirmation before implementing,
      unless the change is trivial.

---

# 4. Implement

- [ ] One logical change at a time.
- [ ] Minimal diff.
- [ ] No unrelated refactoring.
- [ ] Imports at the top of the file.
- [ ] Thread-safe for:
  - `pygame`
  - `pyaudio`
  - `synthesizer`
- [ ] gRPC proto/stubs/client/server kept in sync.
- [ ] WinUI XAML binding and `MainViewModel` updated together.

Compile after each logical step:

Python:

```bash
py -3.12 -m py_compile <file>

WinUI:

dotnet build src/TARNO.UI/TARNO.UI.csproj -c Debug -p:Platform=x64
5. Verify

Before completion:

 Runtime-tested for 15-30 seconds.
 Logs clean.
 No new warnings or errors.
 Existing behavior not broken.
 pyinstaller build still works if Python changed.
 WinUI still builds if XAML/C# changed.
 New resources added to:
tarno.spec
TARNO.UI.csproj
6. Review

Final review:

 Summarize what changed.
 List modified files.
 Provide copy-pastable verification command.
 Update todo list.
 Confirm no unrelated changes were introduced.

Language rules:

German for UI/log strings.
English for code identifiers.