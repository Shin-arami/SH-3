# SH-3 Relationship: inferred_from

Version: 1.0.0
Status: Stable
Category: Ontology Relationship
Relationship ID: REL-0402
Canonical Name: inferred_from
Predicate: inferred_from
Inverse Predicate: inference_source_of
Author: SH-3 Architecture Working Group

---

# 1. Overview

The **inferred_from** relationship represents the canonical semantic
association between a conclusion and the evidence, facts, or knowledge
from which it is logically inferred.

Unlike **derived_from**, which represents provenance and transformation,
**inferred_from** represents reasoning.

The relationship captures semantic inference independently of the
reasoning algorithm.

---

# 2. Purpose

The inferred_from relationship enables:

- Logical reasoning
- Semantic inference
- Knowledge graph reasoning
- Explainable AI
- Decision justification
- Rule evaluation
- Knowledge discovery
- Cognitive traceability

Every inferred entity SHALL reference one or more supporting premises.

---

# 3. Canonical Definition

A subject **inferred_from** one or more objects when the subject is
logically concluded from those objects through an explicit reasoning
process.

Inference MAY use deductive, inductive, abductive, probabilistic,
statistical, symbolic, or hybrid reasoning.

---

# 4. Characteristics

The **inferred_from** relationship SHALL be:

- Directed
- Explainable
- Traceable
- Deterministic (for deterministic reasoning engines)
- Machine readable
- Versioned

Inference SHALL preserve reasoning provenance.

---

# 5. Relationship Signature

```text
Inference

inferred_from

Evidence
```

---

# 6. Semantic Meaning

The inferred entity represents a conclusion rather than a transformed
copy of the source.

The evidence SHALL remain independently identifiable.

Inference SHALL preserve reasoning explainability.

---

# 7. Inverse Relationship

```text
Evidence

inference_source_of

Inference
```

The inverse relationship SHALL preserve semantic consistency.

---

# 8. Multiplicity

Supported cardinalities include:

- 1 → 1
- N → 1
- N → N

Multiple evidence sources MAY contribute to the same inference.

---

# 9. Valid Examples

## Rule Engine

```text
Decision

inferred_from

PolicyRule
```

---

## Knowledge Graph

```text
Relationship

inferred_from

KnowledgeGraph
```

---

## AI Reasoning

```text
Hypothesis

inferred_from

Evidence
```

---

## Planning

```text
ExecutionStrategy

inferred_from

MissionContext
```

---

## Diagnosis

```text
FailureCause

inferred_from

SystemMetrics
```

---

# 10. Invalid Examples

The following SHOULD NOT use **inferred_from**.

```text
Summary

inferred_from

Document
```

Use **derived_from**.

---

```text
PlannerService

inferred_from

MemoryService
```

Use **uses**.

---

```text
Task

inferred_from

Mission
```

Use **part_of**.

---

# 11. Reasoning Semantics

Inference SHOULD preserve:

- Evidence identifiers
- Rule identifiers
- Reasoning strategy
- Confidence
- Timestamp
- Provenance
- Explanation

Reasoning SHALL remain reproducible when deterministic inputs are used.

---

# 12. Supported Reasoning Models

Reasoning MAY include:

- Deduction
- Induction
- Abduction
- Bayesian inference
- Statistical inference
- Rule-based inference
- Ontological reasoning
- LLM-assisted reasoning

Reasoning type SHOULD be recorded.

---

# 13. Registry Integration

The inferred_from relationship SHALL integrate with:

- KG Registry
- MEM Registry
- SEM Registry
- XRF Registry

Metadata MAY include:

```yaml
inference:
evidence:
reasoning_engine:
reasoning_type:
confidence:
timestamp:
trace_id:
```

---

# 14. Federation

Federated SH-3 systems SHALL preserve inference provenance.

Federation SHALL preserve:

- Evidence identity
- Confidence
- Trust
- Version
- Traceability

Inference provenance SHALL remain verifiable across federation members.

---

# 15. Constraints

The **inferred_from** relationship SHALL:

- Preserve evidence identity
- Preserve reasoning provenance
- Support explainability
- Support auditing
- Remain implementation independent

The relationship SHALL NOT imply:

- Transformation
- Ownership
- Execution
- Structural composition

---

# 16. Relationship Comparison

| Relationship | Meaning |
|--------------|---------|
| derived_from | Origin or transformation |
| inferred_from | Logical conclusion |
| references | Citation or linkage |
| supports | Supporting evidence |

---

# 17. Examples

## Rule Evaluation

```text
Facts

↓

Rule Engine

↓

Decision

inferred_from

Facts
```

---

## Knowledge Graph Reasoning

```text
Knowledge Graph

↓

Reasoner

↓

New Relationship

inferred_from

Knowledge Graph
```

---

## Failure Analysis

```text
Metrics

↓

Diagnostic Engine

↓

Failure Cause

inferred_from

Metrics
```

---

# 18. Reasoning Rules

Reasoning engines MAY maintain inference chains.

```text
Conclusion B

inferred_from

Conclusion A

Conclusion A

inferred_from

Evidence

↓

Conclusion B

indirectly_inferred_from

Evidence
```

Indirect inference SHALL remain distinguishable from direct inference.

---

# 19. Cross References

Related concepts:

- Knowledge
- Evidence
- Rule
- Policy
- Decision
- Reasoning Engine
- Knowledge Graph

Related relationships:

- derived_from
- references
- supports
- inference_source_of

Referenced specifications:

- Knowledge Architecture
- Reasoning Architecture
- Knowledge Graph
- Memory Architecture
- RFC-0269 Semantic Intelligence Layer

---

# 20. Summary

The **inferred_from** relationship defines the canonical semantic
association between a conclusion and the evidence from which it is
logically inferred within the SH-3 Ontology.

It establishes the semantic foundation for explainable reasoning,
knowledge graph inference, decision justification, cognitive
traceability, and auditable AI reasoning while preserving deterministic,
implementation-independent semantics.