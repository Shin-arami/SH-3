# SH-3 Relationship: schedules

Version: 1.0.0
Status: Stable
Category: Ontology Relationship
Relationship ID: REL-0303
Canonical Name: schedules
Predicate: schedules
Inverse Predicate: scheduled_by
Author: SH-3 Architecture Working Group

---

# 1. Overview

The **schedules** relationship represents the canonical semantic
association in which a scheduling authority determines when, how, and
under which execution policy another executable entity will execute.

Unlike **executes**, which performs execution, **schedules** determines
execution order and timing.

Scheduling is concerned with execution planning rather than execution
itself.

---

# 2. Purpose

The schedules relationship enables:

- Task scheduling
- Workflow orchestration
- Mission planning
- Runtime dispatching
- Pipeline coordination
- Resource allocation
- Priority management
- Deterministic execution ordering

Scheduling SHALL precede execution.

---

# 3. Canonical Definition

A subject **schedules** an object when the subject determines the
execution plan for that object.

Scheduling MAY define execution timing, priority, placement,
dependencies, retries, deadlines, and execution policies.

Scheduling SHALL NOT itself execute the scheduled entity.

---

# 4. Characteristics

The **schedules** relationship SHALL be:

- Directed
- Behavioral
- Deterministic
- Explainable
- Observable
- Machine readable
- Versioned

Scheduling SHALL preserve execution independence.

---

# 5. Relationship Signature

```text
Scheduler

schedules

Executable Entity
```

---

# 6. Semantic Meaning

The scheduler establishes an execution plan.

Scheduling MAY specify:

- Priority
- Execution time
- Deadline
- Retry policy
- Timeout
- Placement
- Resource limits
- Execution policy

Execution remains the responsibility of the executor.

---

# 7. Inverse Relationship

```text
Executable Entity

scheduled_by

Scheduler
```

The inverse relationship SHALL preserve identical scheduling semantics.

---

# 8. Multiplicity

Supported cardinalities include:

- 1 → 1
- 1 → N
- N → N

Scheduling conflicts SHALL be resolved by Runtime Policy.

---

# 9. Valid Examples

## Runtime

```text
Runtime

schedules

Task
```

---

## Scheduler

```text
PriorityScheduler

schedules

Workflow
```

---

## Agent

```text
CoordinatorAgent

schedules

Mission
```

---

## Pipeline

```text
PipelineScheduler

schedules

PipelineStage
```

---

## Federation

```text
FederationScheduler

schedules

DistributedTask
```

---

# 10. Invalid Examples

The following SHOULD NOT use **schedules**.

```text
Runtime

schedules

Capability
```

Use **provides** or **requires**.

---

```text
PlannerService

schedules

MemoryService
```

Use **invokes** if requesting execution.

---

```text
Mission

schedules

Goal
```

Use **contains**.

---

# 11. Scheduling Lifecycle

Scheduling MAY progress through:

```text
Created

↓

Queued

↓

Prioritized

↓

Allocated

↓

Ready

↓

Dispatched
```

Execution begins only after dispatch.

---

# 12. Scheduling Policy

Scheduling MAY consider:

- Priority
- Cost
- Latency
- Resource availability
- Affinity
- Trust
- Security
- Federation topology

Policy evaluation SHALL be deterministic.

---

# 13. Observability

Scheduling SHOULD expose:

- Schedule ID
- Queue position
- Priority
- Estimated start time
- Deadline
- Assigned executor
- Retry policy
- Scheduling latency

Scheduling SHALL support runtime diagnostics.

---

# 14. Registry Integration

The schedules relationship SHALL integrate with:

- EVT Registry
- MOD Registry
- SEM Registry
- CAP Registry

Metadata MAY include:

```yaml
scheduler:
target:
priority:
deadline:
execution_policy:
queue:
trace_id:
```

---

# 15. Federation

Federated SH-3 systems MAY schedule workloads across multiple nodes.

Federation SHALL preserve:

- Scheduling semantics
- Provenance
- Trust
- Execution policy
- Traceability

Distributed scheduling SHALL remain deterministic.

---

# 16. Constraints

The **schedules** relationship SHALL:

- Represent execution planning
- Preserve execution independence
- Support deterministic ordering
- Support observability
- Remain implementation independent

The relationship SHALL NOT imply:

- Execution
- Invocation
- Ownership
- Capability implementation

---

# 17. Relationship Comparison

| Relationship | Meaning |
|--------------|---------|
| executes | Performs execution |
| invokes | Requests execution |
| schedules | Plans execution |
| requires | Declares dependency |
| uses | Utilizes a capability |
| consumes | Processes execution input |

---

# 18. Examples

## Runtime Scheduling

```text
PriorityScheduler

schedules

Task

↓

Runtime

executes

Task
```

---

## Mission Scheduling

```text
MissionPlanner

schedules

Mission

↓

Agent

executes

Mission
```

---

## Federation Scheduling

```text
FederationScheduler

schedules

DistributedWorkflow

↓

Remote Runtime

executes

DistributedWorkflow
```

---

# 19. Reasoning Rules

Reasoning engines MAY infer:

```text
Scheduler

schedules

Task

↓

Task

will_be_executed_by

Runtime
```

Execution responsibility SHALL NOT be inferred from scheduling alone
unless an explicit execution assignment exists.

---

# 20. Cross References

Related concepts:

- Runtime
- Scheduler
- Task
- Workflow
- Pipeline
- Mission
- Agent

Related relationships:

- executes
- invokes
- requires
- uses
- scheduled_by

Referenced specifications:

- Runtime Architecture
- Scheduling Architecture
- Pipeline Architecture
- Event Architecture
- RFC-0261 SH-3 Architecture Framework

---

# 21. Summary

The **schedules** relationship defines the canonical semantic
association between a scheduling authority and an executable entity
within the SH-3 Ontology.

It establishes the semantic foundation for deterministic execution
planning, workflow orchestration, mission coordination, distributed
resource allocation, and runtime scheduling while preserving execution
responsibility, observability, and implementation-independent
architecture.