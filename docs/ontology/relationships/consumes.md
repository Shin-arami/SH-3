# SH-3 Relationship: consumes

Version: 1.0.0
Status: Stable
Category: Ontology Relationship
Relationship ID: REL-0204
Canonical Name: consumes
Predicate: consumes
Inverse Predicate: consumed_by
Author: SH-3 Architecture Working Group

---

# 1. Overview

The **consumes** relationship represents the canonical semantic
association between a consumer and an input entity that is processed,
accepted, transformed, or exhausted during execution.

Unlike **uses**, which denotes interaction without implying modification,
**consumes** denotes the semantic processing of an input.

The consumed entity may be transformed, acknowledged, removed from a
queue, or incorporated into another result according to execution
semantics.

---

# 2. Purpose

The consumes relationship enables:

- Input processing
- Event consumption
- Message handling
- Data stream processing
- Resource utilization
- Pipeline execution
- Runtime observability
- Semantic reasoning

Every consumed entity SHALL participate in an execution context.

---

# 3. Canonical Definition

A subject **consumes** an object when the object serves as an execution
input that is processed by the subject.

Consumption describes the semantic role of the object during execution,
not its physical destruction.

---

# 4. Characteristics

The **consumes** relationship SHALL be:

- Directed
- Behavioral
- Observable
- Deterministic
- Explainable
- Machine readable
- Versioned

Consumption SHALL describe runtime processing.

---

# 5. Relationship Signature

```text
Consumer

consumes

Input Entity
```

---

# 6. Semantic Meaning

The subject receives and processes the input entity.

Processing MAY include:

- Reading
- Parsing
- Validation
- Transformation
- Interpretation
- Aggregation
- Routing
- Completion

Consumption SHALL NOT imply ownership.

---

# 7. Inverse Relationship

```text
Input Entity

consumed_by

Consumer
```

The inverse relationship SHALL preserve identical semantics.

---

# 8. Multiplicity

Supported cardinalities include:

- 1 → 1
- 1 → N
- N → N

Multiple consumers MAY consume identical semantic entities when allowed
by Policy.

---

# 9. Valid Examples

## Event Processing

```text
EventHandler

consumes

Event
```

---

## Pipeline

```text
Pipeline

consumes

Task
```

---

## Runtime

```text
Runtime

consumes

ExecutionRequest
```

---

## LLM

```text
LLMService

consumes

Prompt
```

---

## Knowledge Processing

```text
ReasoningEngine

consumes

KnowledgeGraph
```

---

# 10. Invalid Examples

The following SHOULD NOT use **consumes**.

```text
PlannerService

consumes

MemoryService
```

Use **uses**.

---

```text
Plugin

consumes

Capability

(as declaration)
```

Use **requires**.

---

```text
Kernel

consumes

Runtime
```

Use **composed_of** or **contains**.

---

# 11. Runtime Semantics

Consumption MAY generate one or more output entities.

Example:

```text
Prompt

↓

LLM Service

↓

Response
```

The input and output SHALL remain independently identifiable.

---

# 12. Event Semantics

Event processing SHALL preserve:

- Event identifier
- Timestamp
- Provenance
- Correlation ID
- Trace ID

Consumption SHALL NOT invalidate event provenance.

---

# 13. Registry Integration

The consumes relationship SHALL integrate with:

- EVT Registry
- CAP Registry
- MOD Registry
- SEM Registry

Metadata MAY include:

```yaml
consumer:
input:
context:
trace_id:
processing_result:
timestamp:
```

---

# 14. Federation

Federated SH-3 systems MAY consume remote entities.

Federation SHALL preserve:

- Semantic identity
- Provenance
- Trust
- Version
- Traceability

Cross-node consumption SHALL remain observable.

---

# 15. Constraints

The **consumes** relationship SHALL:

- Represent execution input
- Preserve semantic identity
- Support deterministic tracing
- Support explainability
- Remain implementation independent

The relationship SHALL NOT imply:

- Ownership
- Structural composition
- Capability realization
- Service publication

---

# 16. Relationship Comparison

| Relationship | Meaning |
|--------------|---------|
| provides | Makes an entity available |
| requires | Declares a prerequisite |
| uses | Utilizes an existing entity |
| consumes | Processes an execution input |
| executes | Performs execution |

---

# 17. Examples

## Event Processing

```text
EventBus

↓

Event

↓

EventHandler

consumes

Event

↓

Result
```

---

## AI Reasoning

```text
Reasoner

consumes

KnowledgeGraph

↓

Inference
```

---

## LLM Processing

```text
Prompt

↓

LLM Service

consumes

Prompt

↓

Completion
```

---

# 18. Reasoning Rules

Reasoning engines MAY infer:

```text
EventHandler

consumes

Event

↓

EventHandler

uses

Event
```

The inverse inference SHALL NOT be assumed.

Using an entity does not necessarily imply consuming it.

---

# 19. Cross References

Related concepts:

- Event
- Task
- Runtime
- Pipeline
- Knowledge
- Prompt
- Service

Related relationships:

- uses
- requires
- provides
- executes
- invokes
- consumed_by

Referenced specifications:

- Runtime Architecture
- Event Architecture
- Pipeline Architecture
- CAP Registry
- EVT Registry
- RFC-0261 SH-3 Architecture Framework

---

# 20. Summary

The **consumes** relationship defines the canonical semantic association
between an execution component and the inputs it processes within the
SH-3 Ontology.

It establishes the semantic foundation for event handling, pipeline
processing, runtime execution, data-flow modeling, AI inference, and
observable execution while preserving deterministic behavior,
traceability, and implementation-independent semantics.