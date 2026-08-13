---
name: cognitive-kernel-development
description: Use when implementing or modifying TARNO's CognitiveKernel, autonomous task execution, goal management, planning systems, decision engines, policy layers, agent control loops, or systems requiring separation between LLM reasoning and deterministic execution.
---

# TARNO Cognitive Kernel Development

Triggered whenever work affects TARNO's autonomous cognition layer.

This skill defines the engineering principles for building TARNO's Cognitive Kernel: a deterministic control layer that enables persistent goals, autonomous task execution, planning support, and safe agent behavior without giving the language model direct authority over system actions.

The Cognitive Kernel is not an LLM wrapper.
It is an executive control system around probabilistic reasoning.

---

# Core Philosophy

Traditional AI assistants follow:


User Input
↓
LLM Response
↓
Action


TARNO follows:


User Input
↓
Cognitive Kernel
↓
Decision / Policy Evaluation
↓
LLM Reasoning (proposal only)
↓
Validation
↓
Execution Authority
↓
TarnoEngine
↓
Tools / System


The LLM provides intelligence.
The Kernel provides control.

---

# Fundamental Rules

## 1. LLM Has No Execution Authority

The language model must never directly:

- execute tools
- modify goals
- change system state
- bypass policies
- alter permissions
- cancel safety mechanisms

The LLM output is always considered untrusted.

Allowed:


LLM
↓
ReasoningResult
↓
ActionProposal
↓
PolicyEngine
↓
ExecutionInstruction


Forbidden:


LLM
↓
execute_tool()


---

# 2. Active Goals Are Kernel-Owned State

An active goal belongs exclusively to deterministic kernel code.

The LLM may:

- suggest plans
- suggest next actions
- provide reasoning

The LLM may not:

- overwrite ActiveGoal
- remove constraints
- change task priority
- unlock protected state

State mutation happens only through controlled kernel methods.

---

# 3. Task Commitment Model

Once a goal is accepted:


ActiveGoal
|
v
Execution Pipeline


The kernel maintains commitment until:

- goal completion
- verified failure
- explicit user cancellation
- safety interrupt
- authorized system override

Normal conversational input does not automatically replace an active goal.

Example:

Active task:

"Install and configure TARNO"

User says:

"Tell me a joke"

Correct behavior:


buffered_inputs += joke_request

continue installation task


After task checkpoint:


process buffered input


---

# 4. Cognitive Separation

Keep these systems separate:

## Reasoning Layer

Responsible for:

- interpretation
- planning suggestions
- analysis
- strategy

Implemented through:


ReasoningResult
ActionProposal


---

## Policy Layer

Responsible for:

- permissions
- safety decisions
- autonomy limits
- validation

Implemented through:


PolicyEngine


---

## Execution Layer

Responsible for:

- state mutation
- task progression
- calling TarnoEngine

Implemented through:


ExecutionLoop
ExecutionInstruction


---

# Architecture Requirements

When extending CognitiveKernel prefer:


tarno/core/kernel/

goals/
    Goal models
    Goal repository

reasoning/
    LLM interfaces
    proposals

policy/
    permissions
    interrupts
    validation

execution/
    instructions
    execution loop
    verification

planning/
    future planning systems

memory/
    reflection and experience systems

Do not create one giant `kernel.py`.

---

# Adding New Capabilities

Before implementing:

Answer:

1. Is this cognition?
2. Is this execution?
3. Is this policy?
4. Is this memory?
5. Is this interface?

Place the feature in the correct layer.

---

# Verification Requirements

Every autonomous action requires:

1. Proposal generation


"What should happen?"


2. Policy validation


"Is this allowed?"


3. Execution decision


"Perform this controlled action"


4. Verification


"Did the expected result happen?"


Never skip validation because the action appears harmless.

---

# Safety Interrupts

The Kernel must always support:

- USER_CANCEL
- SAFETY_STOP
- SHUTDOWN

User cancellation and safety mechanisms have priority over autonomy.

An autonomous system without interruption capability is considered incorrectly designed.

---

# Persistence and Memory

Future autonomy requires:

- goal persistence
- experience storage
- reflection
- learned strategies

However:

Do not implement artificial memory shortcuts.

Prefer explicit interfaces:


GoalRepository
MemoryRepository
ReflectionStore


over hidden global state.

---

# Development Workflow

For every Cognitive Kernel change:

1. Read existing architecture first.
2. Identify affected layer.
3. Write or update design plan.
4. Implement smallest isolated component.
5. Add tests.
6. Verify integration.
7. Only then expand functionality.

Never implement a complete autonomous subsystem in one untested step.

---

# Anti Patterns

## God Agent

Bad:


One LLM controls:

planning
memory
tools
permissions
execution

Reason:

No reliable control boundary.

---

## Prompt-Based Safety

Bad:

"System prompt tells the AI not to do dangerous things."

Reason:

Prompts are not security boundaries.

---

## Infinite Autonomous Loop

Bad:


while True:
ask LLM what to do


Reason:

No objective control, no verification, no stopping conditions.

---

## Hidden State Mutation

Bad:


LLM changes active_goal directly


Correct:


Proposal
↓
Policy
↓
Kernel Mutation


---

# Long-Term Vision

Cognitive Kernel is the foundation for future TARNO capabilities:

- persistent autonomous goals
- multi-step planning
- self-evaluation
- adaptive strategies
- experience-based improvement
- agent collaboration

Future extensions must preserve the fundamental rule:

"The model thinks. The Kernel decides. The Engine executes."