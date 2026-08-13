# Review Rubric for TARNO Answers

Use this to judge whether a TARNO plan, architecture review or implementation
is good enough to deliver.

---

# Architecture Review Quality

Use this when reviewing TARNO plans or frozen architecture.

## Preservation of Decisions

- [ ] Existing architecture decisions are respected.
- [ ] The reviewer does not redesign without evidence.
- [ ] Findings are separated from suggestions.
- [ ] Scope expansion is avoided.
- [ ] Critical issues are distinguished from preferences.

## Consistency

- [ ] Every component has a clear responsibility.
- [ ] Ownership boundaries are explicit.
- [ ] Data flow is understandable.
- [ ] State transitions are complete.
- [ ] Concurrency assumptions are documented.
- [ ] Failure states are considered.
- [ ] Shutdown and recovery behavior are defined.

## Feasibility

- [ ] The architecture can realistically be implemented.
- [ ] Dependencies exist or have alternatives.
- [ ] Interfaces and contracts are realistic.
- [ ] The design matches the actual project constraints.

## Finding Quality

Every finding should include:

- [ ] Severity level.
- [ ] Exact location.
- [ ] Clear problem description.
- [ ] Reason why it matters.
- [ ] Recommended correction.

Avoid:

- [ ] Vague criticism.
- [ ] Personal preference presented as a bug.
- [ ] Complete rewrites without justification.

---

# Correctness

- [ ] The backend/frontend used by the request is correctly identified.
- [ ] The active launch mode is respected:
  - PySide6
  - Console
  - OVOS
  - gRPC/WinUI

- [ ] Config values are read from:
  - `config/default.yaml`
  - actual runtime `TarnoConfig`

- [ ] Line numbers and file paths cited are correct.

---

# Completeness

- [ ] All files that need to change are listed.
- [ ] For UI changes:
  - XAML
  - ViewModel
  - Code-behind

  are considered.

- [ ] For gRPC changes:
  - proto
  - Python stubs
  - server
  - C# client

  are considered.

- [ ] For packaging changes:
  - `tarno.spec`
  - PyInstaller
  - NSIS installer

  are considered.

- [ ] Verification steps are concrete and executable.

---

# Side Effects

- [ ] The voice pipeline is traced end-to-end before changes.
- [ ] Thread safety is considered for:
  - `pygame`
  - `pyaudio`
  - `synthesizer`

- [ ] Audio lifecycle is preserved:
  - start
  - stop
  - read_chunk

- [ ] Existing settings and cached data are not overwritten accidentally.

- [ ] Cross-layer side effects are considered.

---

# Minimalism

- [ ] The smallest change solving the problem is chosen.
- [ ] No unrelated refactoring.
- [ ] No unnecessary renaming.
- [ ] No new dependencies unless required.

---

# Communication

- [ ] Reasoning is shown before implementation.
- [ ] Current state is explained.
- [ ] Affected files are listed.
- [ ] Verification commands are provided.
- [ ] Final status is summarized.

Language rules:

- German UI/log strings.
- English code identifiers.

---

# Implementation Quality

- [ ] The implementation follows the approved plan.
- [ ] Changes are incremental.
- [ ] Each step is verified.
- [ ] Build results are reported.
- [ ] Runtime behavior is tested.

---

# Red Flags

## Architecture

- [ ] Changing frozen architecture without approval.
- [ ] Ignoring existing design constraints.
- [ ] Adding components without necessity.
- [ ] Treating preferences as critical bugs.

## Code

- [ ] Citing a file that does not exist.
- [ ] Ignoring the actual launch mode.
- [ ] Recommending config changes that are ignored at runtime.
- [ ] Forgetting thread synchronization around audio components.
- [ ] Breaking gRPC contracts.
- [ ] Forgetting resource updates for packaging.

## TARNO Specific

- [ ] Using `pygame.mixer.music` for short overlapping confirmation sounds.
- [ ] Forgetting locks around `pygame` operations.
- [ ] Breaking `_sanitize_for_speech()`.
- [ ] Proposing WinUI-only solutions when backend behavior is involved.
- [ ] Changing CPU-first policy:
  `ollama.num_gpu: 0`