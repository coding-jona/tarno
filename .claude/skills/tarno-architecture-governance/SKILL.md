\---

name: tarno-architecture-governance

description: Use before making architectural changes to TARNO including new modules, refactors, engine changes, layer changes, dependency decisions, or features affecting core systems. Ensures changes preserve TARNO's architecture boundaries and existing functionality before implementation.

\---



\# TARNO Architecture Governance



Triggered before any architectural modification to the TARNO system.



This skill exists to prevent accidental architecture drift, destructive refactoring, and mixing responsibilities between TARNO's execution, cognition, interface, and infrastructure layers.



TARNO is not developed as a collection of isolated features. Each component has a defined responsibility and changes must preserve these boundaries.



\## Why this exists



During TARNO development, several architectural risks were identified:



\- Replacing `TarnoEngine` with a generic agent framework would remove existing voice, LLM provider switching, tool execution, and memory functionality.

\- Large AI-generated refactors can improve local code quality while silently damaging system architecture.

\- Similar responsibilities must not be duplicated across multiple layers.



Therefore, architectural changes require analysis before implementation.



\## Core Architecture Rules



\### Execution Layer



`TarnoEngine` is the execution body of TARNO.



Responsibilities:

\- Voice interaction flow

\- LLM provider communication

\- Tool execution coordination

\- Conversation processing

\- Runtime orchestration



Do not replace or redesign `TarnoEngine` without explicit architectural approval.



\---



\### Cognitive Layer



Future autonomous capabilities belong outside the execution layer.



Examples:

\- Goals

\- Planning

\- Reflection

\- Decision making

\- Long-term autonomy



These systems must be implemented as separate modules that control execution rather than replacing it.



\---



\### Interface Layer



UI and communication layers are consumers of TARNO capabilities.



Examples:

\- WinUI 3 frontend

\- gRPC bridge

\- PySide6 interface



Do not place business logic inside UI layers.



\---



\## Required Process



Before implementing an architectural change:



1\. Identify the affected layers:

&#x20;  - Core execution

&#x20;  - Cognitive systems

&#x20;  - Memory

&#x20;  - Tools

&#x20;  - Voice

&#x20;  - UI

&#x20;  - Infrastructure



2\. Inspect existing implementations before designing replacements.



3\. Determine whether the change is:

&#x20;  - additive

&#x20;  - modifying

&#x20;  - replacing



4\. Prefer additive architecture over destructive replacement.



5\. Create an implementation plan before writing code.



6\. Identify:

&#x20;  - dependencies

&#x20;  - migration risks

&#x20;  - backwards compatibility concerns

&#x20;  - required tests



7\. Only implement after the architectural decision is clear.



\---



\## Decision Rules



Prefer:



\- New modules over modifying stable core files.

\- Interfaces over hard dependencies.

\- Feature flags over breaking changes.

\- Incremental migration over rewrites.

\- Tests before large integration changes.



Avoid:



\- "Clean rewrites" of working systems.

\- Moving unrelated responsibilities into one module.

\- Creating duplicate systems without justification.

\- Removing existing functionality to implement a theoretical architecture.



\---



\## Anti-patterns



Avoid these approaches:



\### Generic Agent Replacement



Bad:





Replace TarnoEngine with AgentLoop()





Reason:

Destroys existing capabilities.



Correct:





CognitiveKernel

|

v

TarnoEngine

|

v

Tools / Voice / Memory





\---



\### Prompt-Based Authority



Bad:





LLM decides:



modify files

execute commands

change system state



Correct:





LLM suggestion

|

Policy validation

|

Deterministic execution





\---



\### Architecture Without Reality Check



Bad:



Designing new systems without checking:

\- current code

\- existing modules

\- runtime paths

\- tests



Correct:



Inspect → Analyze → Plan → Implement → Verify



\---



\## Documentation Requirements



For significant architecture decisions create or update:



\- Architecture Decision Records (ADR)

\- Relevant documentation under `/docs`

\- Tests proving the intended behavior



Document:

\- Why the decision was made

\- Alternatives considered

\- Trade-offs

\- Future migration path



\---



\## TARNO Architecture Decisions



\### ADR-001: TarnoEngine remains execution layer



Date:

2026-07-21



Decision:



TarnoEngine remains responsible for runtime execution.



Autonomous cognition is implemented as a separate control layer.



Reason:



Existing TarnoEngine contains critical functionality:

\- Voice pipeline

\- LLM providers

\- Tools

\- Memory handling

\- Runtime coordination



Replacing it would create unnecessary regression risk.



\---



\### ADR-002: Additive evolution over replacement



TARNO evolves through additional layers instead of replacing working foundations.



New capabilities should wrap, extend, or orchestrate existing systems.



