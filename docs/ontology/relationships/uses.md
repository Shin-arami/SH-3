# SH-3 Relationship: uses

Version: 1.0.0
Status: Stable
Category: Ontology Relationship
Relationship ID: REL-0203
Canonical Name: uses
Predicate: uses
Inverse Predicate: used_by
Author: SH-3 Architecture Working Group

---

# 1. Overview

The **uses** relationship represents the canonical semantic association
between a consumer and a semantic entity that it actively utilizes while
performing its behavior.

Unlike **requires**, which declares a prerequisite,
**uses** represents actual semantic utilization.

The relationship models runtime interaction rather than dependency
declaration.

---

# 2. Purpose

The uses relationship provides:

- Runtime utilization
- Capability consumption
- Service interaction
- Resource access
- Knowledge usage
- Policy evaluation
- Explainable execution
- Runtime tracing

Every use SHALL occur within an execution context.

---

# 3. Canonical Definition

A subject **uses** an object when the subject actively interacts with the
object while performing its intended behavior.

The object SHALL remain semantically independent of the consumer.

---

# 4. Characteristics

The **uses** relationship SHALL be:

- Directed
- Behavioral
- Observable
- Deterministic
- Machine readable
- Explainable
- Versioned

The relationship SHALL describe runtime utilization.

---

# 5. Relationship Signature

```text
Consumer

uses

Target Entity
```

---

# 6. Semantic Meaning

The subject performs one or more interactions with the target entity.

The interaction MAY involve:

- Invocation
- Query
- Reading
- Writing
- Evaluation
- Retrieval

The relationship SHALL NOT imply ownership or implementation.

---

# 7. Inverse Relationship

```text
Target Entity

used_by

Consumer
```

Both predicates SHALL preserve identical semantic meaning.

---

# 8. Multiplicity

Supported cardinalities include:

- 1 → 1
- 1 → N
- N → N

Multiple consumers MAY simultaneously use the same semantic entity.

---

# 9. Valid Examples

## Service Usage

```text
PlannerService

uses

MemoryService
```

---

## Agent Usage

```text
Agent

uses

PlanningCapability
```

---

## Runtime Usage

```text
Runtime

uses

EventBus
```

---

## Mission Usage

```text
Mission

uses

KnowledgeBase
```

---

## Plugin Usage

```text
TranslationPlugin

uses

LLMCapability
```

---

# 10. Invalid Examples

The following SHOULD NOT use **uses**.

```text
PlannerService

uses

PlanningCapability

(as declaration)
```

Use **requires** or **implements**.

---

```text
Kernel

uses

Runtime

(as composition)
```

Use **composed_of**.

---

```text
Capability

uses

Service
```

Use **implemented_by** or **provided_by**.

---

# 11. Runtime Semantics

The **uses** relationship SHALL exist only within an execution context.

Runtime MAY record:

- Start time
- End time
- Duration
- Invocation count
- Result
- Failure
- Trace identifier

Usage events SHOULD be observable.

---

# 12. Runtime Traceability

Each use MAY produce observable events.

Example:

```text
PlannerService

uses

MemoryService

↓

MemoryQueryEvent

↓

KnowledgeRetrievedEvent
```

Tracing SHALL support deterministic replay.

---

# 13. Registry Integration

The relationship SHALL integrate with:

- CAP Registry
- MOD Registry
- EVT Registry
- SEM Registry

Metadata MAY include:

```yaml
consumer:
target:
context:
timestamp:
trace_id:
duration:
```

---

# 14. Federation

Federated SH-3 systems MAY use remote semantic entities.

Federation SHALL preserve:

- Semantic identity
- Traceability
- Provenance
- Version
- Trust

Remote usage SHALL remain observable.

---

# 15. Constraints

The **uses** relationship SHALL:

- Represent active utilization
- Preserve semantic identity
- Support runtime tracing
- Support observability
- Remain implementation independent

The relationship SHALL NOT imply:

- Ownership
- Structural composition
- Capability implementation
- Dependency declaration

---

# 16. Relationship Comparison

| Relationship | Meaning |
|--------------|---------|
| implements | Realizes a semantic contract |
| provides | Makes an entity available |
| requires | Declares a prerequisite |
| uses | Performs active utilization |
| executes | Performs execution |

---

# 17. Examples

## Capability Utilization

```text
PlannerService

requires

MemoryCapability

↓

Runtime Resolution

↓

MemoryService

↓

PlannerService

uses

MemoryService
```

---

## Runtime Interaction

```text
Runtime

uses

Scheduler

↓

Scheduler

uses

EventBus
```

---

## Agent Execution

```text
Agent

uses

ReasoningService

↓

ReasoningService

uses

KnowledgeBase
```

---

# 18. Reasoning Rules

Reasoning engines MAY infer:

```text
PlannerService

uses

MemoryService

MemoryService

provides

MemoryCapability

↓

PlannerService

uses

MemoryCapability
```

Reasoning SHALL preserve semantic consistency.

---

# 19. Cross References

Related concepts:

- Capability
- Service
- Runtime
- Agent
- Mission
- Event
- Knowledge

Related relationships:

- provides
- requires
- implements
- executes
- invokes
- used_by

Referenced specifications:

- CAP Registry
- EVT Registry
- Runtime Architecture
- Service Discovery
- Plugin API
- SDK
- RFC-0261 SH-3 Architecture Framework

---

# 20. Summary

The **uses** relationship defines the canonical semantic association
between a consumer and the capabilities, services, resources, or
knowledge it actively utilizes during execution.

It establishes the semantic foundation for runtime interaction,
observability, tracing, capability utilization, and explainable
execution while preserving deterministic behavior and
implementation-independent architecture throughout the SH-3 ecosystem.