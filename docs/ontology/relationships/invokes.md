# SH-3 Relationship: invokes

Version: 1.0.0
Status: Stable
Category: Ontology Relationship
Relationship ID: REL-0302
Canonical Name: invokes
Predicate: invokes
Inverse Predicate: invoked_by
Author: SH-3 Architecture Working Group

---

# 1. Overview

The **invokes** relationship represents the canonical semantic
association in which one executable entity requests another executable
entity to perform work.

Unlike **executes**, which expresses execution responsibility,
**invokes** expresses delegation of execution.

The invoker initiates execution but does not become the executor.

---

# 2. Purpose

The invokes relationship enables:

- Service invocation
- Agent collaboration
- Workflow orchestration
- Pipeline execution
- Plugin invocation
- Tool execution
- Distributed execution
- Event-driven coordination

Invocation SHALL preserve execution boundaries.

---

# 3. Canonical Definition

A subject **invokes** an object when the subject requests the object to
perform an executable operation.

The invoked entity SHALL remain responsible for its own execution.

Invocation SHALL NOT transfer execution ownership.

---

# 4. Characteristics

The **invokes** relationship SHALL be:

- Directed
- Behavioral
- Observable
- Traceable
- Explainable
- Machine readable
- Versioned

Invocation SHALL create an execution relationship without changing
execution responsibility.

---

# 5. Relationship Signature

```text
Invoker

invokes

Executable Entity
```

---

# 6. Semantic Meaning

The subject initiates execution by requesting another executable entity.

Invocation MAY be:

- Synchronous
- Asynchronous
- Local
- Remote
- Event-driven
- Scheduled

The invoked entity determines how execution proceeds.

---

# 7. Inverse Relationship

```text
Executable Entity

invoked_by

Invoker
```

Both predicates SHALL describe identical invocation semantics from
opposite directions.

---

# 8. Multiplicity

Supported cardinalities include:

- 1 → 1
- 1 → N
- N → N

Recursive invocation MAY be permitted when governed by Runtime Policy.

---

# 9. Valid Examples

## Service Invocation

```text
PlannerService

invokes

MemoryService
```

---

## Agent Collaboration

```text
CoordinatorAgent

invokes

WorkerAgent
```

---

## Runtime

```text
Runtime

invokes

Pipeline
```

---

## Plugin

```text
Plugin

invokes

Extension
```

---

## Tool

```text
ReasoningService

invokes

SearchTool
```

---

# 10. Invalid Examples

The following SHOULD NOT use **invokes**.

```text
Runtime

invokes

Capability
```

Use **uses** or **requires**.

---

```text
Mission

invokes

Goal
```

Use **contains**.

---

```text
Kernel

invokes

Runtime

(as structural relationship)
```

Use **contains** or **part_of**.

---

# 11. Invocation Lifecycle

Invocation MAY progress through:

```text
Requested

↓

Accepted

↓

Executing

↓

Completed
```

Alternative terminal states include:

- Rejected
- Failed
- Cancelled
- Timed Out

Lifecycle transitions SHOULD generate Events.

---

# 12. Execution Context

Invocation SHALL preserve:

- Trace ID
- Correlation ID
- Parent Execution ID
- Context ID
- Security Context
- Policy Context

Context propagation SHALL be deterministic.

---

# 13. Observability

Invocation SHOULD expose:

- Invocation ID
- Target
- Caller
- Timestamp
- Duration
- Status
- Retry Count
- Failure Cause

Invocation traces SHALL support end-to-end diagnostics.

---

# 14. Registry Integration

The invokes relationship SHALL integrate with:

- EVT Registry
- MOD Registry
- CAP Registry
- SEM Registry

Metadata MAY include:

```yaml
invoker:
target:
trace_id:
correlation_id:
execution_id:
status:
```

---

# 15. Federation

Federated SH-3 systems MAY invoke remote services.

Federation SHALL preserve:

- Invocation semantics
- Trust
- Provenance
- Traceability
- Version compatibility

Remote invocation SHALL remain observable.

---

# 16. Constraints

The **invokes** relationship SHALL:

- Preserve execution ownership
- Preserve execution context
- Support distributed execution
- Support deterministic tracing
- Remain implementation independent

The relationship SHALL NOT imply:

- Execution responsibility
- Ownership
- Structural composition
- Capability implementation

---

# 17. Relationship Comparison

| Relationship | Meaning |
|--------------|---------|
| executes | Performs execution |
| invokes | Requests execution |
| uses | Utilizes a capability or service |
| consumes | Processes execution input |
| requires | Declares a prerequisite |

---

# 18. Examples

## Service Chain

```text
PlannerService

invokes

MemoryService

↓

MemoryService

invokes

StorageService
```

---

## Agent Collaboration

```text
CoordinatorAgent

invokes

PlannerAgent

↓

PlannerAgent

executes

Mission
```

---

## Remote Invocation

```text
Runtime A

invokes

Runtime B

↓

Runtime B

executes

TranslationService
```

---

# 19. Reasoning Rules

Reasoning engines MAY infer:

```text
PlannerService

invokes

MemoryService

MemoryService

executes

MemoryQuery

↓

PlannerService

indirectly_depends_on

MemoryQuery
```

Indirect inference SHALL remain distinguishable from direct execution.

---

# 20. Cross References

Related concepts:

- Runtime
- Service
- Agent
- Pipeline
- Workflow
- Tool
- Plugin

Related relationships:

- executes
- schedules
- uses
- requires
- invoked_by

Referenced specifications:

- Runtime Architecture
- Event Architecture
- Pipeline Architecture
- Plugin API
- Service Discovery
- RFC-0261 SH-3 Architecture Framework

---

# 21. Summary

The **invokes** relationship defines the canonical semantic association
between an invoker and an executable target within the SH-3 Ontology.

It establishes the semantic foundation for service orchestration,
workflow coordination, agent collaboration, tool execution, distributed
processing, and event-driven execution while preserving execution
ownership, deterministic behavior, and implementation-independent
architecture.