# SH-3 Relationship: executes

Version: 1.0.0
Status: Stable
Category: Ontology Relationship
Relationship ID: REL-0301
Canonical Name: executes
Predicate: executes
Inverse Predicate: executed_by
Author: SH-3 Architecture Working Group

---

# 1. Overview

The **executes** relationship represents the canonical semantic
association between an execution authority and an executable entity.

It declares that the subject initiates, controls, and completes the
execution lifecycle of the target entity.

Unlike **invokes**, which represents a request to perform behavior,
**executes** represents responsibility for execution.

---

# 2. Purpose

The executes relationship enables:

- Runtime execution
- Task execution
- Mission execution
- Workflow execution
- Pipeline execution
- Agent execution
- Kernel coordination
- Execution tracing

Every execution SHALL occur within an Execution Context.

---

# 3. Canonical Definition

A subject **executes** an object when the subject is responsible for
performing the complete execution lifecycle of the object.

Execution includes initialization, scheduling, monitoring, completion,
and failure handling where applicable.

---

# 4. Characteristics

The **executes** relationship SHALL be:

- Directed
- Behavioral
- Observable
- Deterministic
- Traceable
- Machine readable
- Versioned

Execution SHALL produce observable lifecycle events.

---

# 5. Relationship Signature

```text
Executor

executes

Executable Entity
```

---

# 6. Semantic Meaning

The executor controls execution of the target.

Execution MAY include:

- Initialization
- Validation
- Resource allocation
- Scheduling
- Monitoring
- Completion
- Retry
- Cancellation
- Recovery

Execution responsibility remains with the executor.

---

# 7. Inverse Relationship

```text
Executable Entity

executed_by

Executor
```

Both predicates SHALL describe the same execution semantics from opposite
directions.

---

# 8. Multiplicity

Supported cardinalities include:

- 1 → 1
- 1 → N
- N → N

Parallel execution SHALL be explicitly governed by Runtime Policy.

---

# 9. Valid Examples

## Runtime

```text
Runtime

executes

Service
```

---

## Scheduler

```text
Scheduler

executes

Task
```

---

## Agent

```text
Agent

executes

Mission
```

---

## Kernel

```text
Kernel

executes

Workflow
```

---

## Pipeline

```text
Pipeline

executes

Stage
```

---

# 10. Invalid Examples

The following SHOULD NOT use **executes**.

```text
PlannerService

executes

MemoryCapability
```

Use **uses**.

---

```text
Plugin

executes

Plugin
```

Use **invokes** if requesting another plugin.

---

```text
Mission

executes

Goal
```

Use **contains** or **composed_of**.

---

# 11. Execution Lifecycle

Execution SHALL progress through a deterministic lifecycle.

```text
Created

↓

Ready

↓

Running

↓

Completed
```

Alternative terminal states MAY include:

- Failed
- Cancelled
- Timed Out
- Suspended

Lifecycle transitions SHOULD generate Events.

---

# 12. Execution Context

Execution MAY include:

- Execution ID
- Context ID
- Correlation ID
- Trace ID
- Parent Execution
- Runtime ID
- Policy ID

Execution context SHALL remain immutable during execution.

---

# 13. Observability

Execution SHOULD expose:

- Start time
- End time
- Duration
- Status
- Retry count
- Failure cause
- Metrics
- Trace information

Execution SHALL support deterministic replay.

---

# 14. Registry Integration

The executes relationship SHALL integrate with:

- EVT Registry
- CAP Registry
- MOD Registry
- SEM Registry

Metadata MAY include:

```yaml
executor:
target:
execution_id:
context:
trace_id:
status:
duration:
```

---

# 15. Federation

Federated SH-3 systems MAY execute workloads on remote members.

Federation SHALL preserve:

- Execution identity
- Provenance
- Trust
- Policy
- Traceability

Distributed execution SHALL remain observable.

---

# 16. Constraints

The **executes** relationship SHALL:

- Represent execution responsibility
- Preserve execution provenance
- Support observability
- Support deterministic replay
- Remain implementation independent

The relationship SHALL NOT imply:

- Ownership
- Capability implementation
- Dependency declaration
- Structural composition

---

# 17. Relationship Comparison

| Relationship | Meaning |
|--------------|---------|
| implements | Realizes a semantic contract |
| provides | Exposes a semantic entity |
| requires | Declares a prerequisite |
| uses | Performs runtime utilization |
| consumes | Processes execution input |
| executes | Performs execution |
| invokes | Requests another execution |

---

# 18. Examples

## Service Execution

```text
Runtime

executes

PlannerService
```

---

## Mission Execution

```text
Agent

executes

Mission

↓

Mission

contains

Goal

↓

Goal

contains

Task
```

---

## Pipeline Execution

```text
Runtime

executes

Pipeline

↓

Pipeline

executes

Stage
```

---

# 19. Reasoning Rules

Reasoning engines MAY infer:

```text
Runtime

executes

PlannerService

PlannerService

provides

PlanningCapability

↓

PlanningCapability

available_during_execution
```

Such inference SHALL preserve execution boundaries and Policy
constraints.

---

# 20. Cross References

Related concepts:

- Runtime
- Kernel
- Agent
- Mission
- Task
- Workflow
- Pipeline
- Service

Related relationships:

- invokes
- schedules
- uses
- consumes
- executed_by

Referenced specifications:

- Runtime Architecture
- Execution Model
- Pipeline Architecture
- Event Architecture
- CAP Registry
- EVT Registry
- RFC-0261 SH-3 Architecture Framework

---

# 21. Summary

The **executes** relationship defines the canonical semantic association
between an execution authority and an executable entity within the SH-3
Ontology.

It establishes the semantic foundation for runtime execution, workflow
coordination, mission execution, pipeline processing, distributed
execution, observability, and deterministic execution management across
the SH-3 ecosystem.