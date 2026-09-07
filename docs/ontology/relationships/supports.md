# SH-3 Relationship: supports

Version: 1.0.0
Status: Stable
Category: Ontology Relationship
Relationship ID: REL-0404
Canonical Name: supports
Predicate: supports
Inverse Predicate: supported_by
Author: SH-3 Architecture Working Group

---

# 1. Overview

The **supports** relationship represents the canonical semantic
association in which one entity provides evidence, justification, or
rationale for another entity.

Unlike **references**, which establishes contextual linkage,
**supports** establishes evidential significance.

Unlike **derived_from**, support does not imply origin.

Unlike **inferred_from**, support does not imply logical deduction.

---

# 2. Purpose

The supports relationship enables:

- Evidence modeling
- Decision justification
- Explainable AI
- Policy validation
- Knowledge verification
- Confidence assessment
- Auditability
- Semantic reasoning

Supporting entities SHALL remain independently verifiable.

---

# 3. Canonical Definition

A subject **supports** an object when the subject contributes evidence,
justification, rationale, observation, or analysis that increases
confidence in the object.

Support SHALL NOT imply proof or causality.

---

# 4. Characteristics

The **supports** relationship SHALL be:

- Directed
- Explainable
- Evidence-oriented
- Machine readable
- Versioned
- Deterministic

Support SHALL preserve evidential independence.

---

# 5. Relationship Signature

```text
Supporting Entity

supports

Supported Entity
```

---

# 6. Semantic Meaning

Support MAY originate from:

- Evidence
- Metrics
- Observations
- Rules
- Policies
- Evaluations
- Test Results
- Expert Analysis

Support SHALL NOT imply derivation or execution.

---

# 7. Inverse Relationship

```text
Supported Entity

supported_by

Supporting Entity
```

The inverse relationship SHALL preserve evidential semantics.

---

# 8. Multiplicity

Supported cardinalities include:

- 1 → 1
- 1 → N
- N → N

Multiple independent entities MAY support the same conclusion.

---

# 9. Valid Examples

## Decision

```text
PerformanceMetrics

supports

OptimizationDecision
```

---

## AI

```text
Evidence

supports

Hypothesis
```

---

## Policy

```text
SecurityRule

supports

AccessDecision
```

---

## Runtime

```text
HealthMetrics

supports

RecoveryDecision
```

---

## Knowledge

```text
Observation

supports

ScientificClaim
```

---

# 10. Invalid Examples

The following SHOULD NOT use **supports**.

```text
Document

supports

Summary

(as provenance)
```

Use **derived_from**.

---

```text
Fact

supports

Conclusion

(as logical deduction)
```

Use **inferred_from** when the relationship represents an explicit
reasoning result.

---

```text
PlannerService

supports

MemoryService

(as runtime interaction)
```

Use **uses**.

---

# 11. Evidence Semantics

Support MAY include:

- Confidence
- Weight
- Reliability
- Source
- Timestamp
- Verification status
- Trust level

Evidence SHALL remain independently identifiable.

---

# 12. Confidence Model

Supporting relationships MAY expose:

```yaml
confidence:
weight:
reliability:
trust:
verification_status:
```

Confidence values SHALL NOT alter the semantic meaning of the predicate.

---

# 13. Registry Integration

The supports relationship SHALL integrate with:

- KG Registry
- MEM Registry
- SEM Registry
- XRF Registry

Metadata MAY include:

```yaml
supporting_entity:
supported_entity:
confidence:
source:
timestamp:
trace_id:
```

---

# 14. Federation

Federated SH-3 systems SHALL preserve:

- Evidence identity
- Confidence
- Provenance
- Trust
- Version

Evidence SHALL remain independently verifiable across federation members.

---

# 15. Constraints

The **supports** relationship SHALL:

- Preserve evidence identity
- Support explainability
- Support auditing
- Support reproducibility
- Remain implementation independent

The relationship SHALL NOT imply:

- Proof
- Origin
- Execution
- Ownership
- Structural composition

---

# 16. Relationship Comparison

| Relationship | Meaning |
|--------------|---------|
| references | Contextual association |
| derived_from | Provenance and origin |
| inferred_from | Logical conclusion |
| supports | Evidence or justification |

---

# 17. Examples

## AI Decision

```text
Sensor Data

supports

ObstacleDetected
```

---

## Runtime Recovery

```text
FailureMetrics

supports

RestartDecision
```

---

## Knowledge Validation

```text
ExperimentalResult

supports

ScientificClaim
```

---

# 18. Reasoning Rules

Reasoning engines MAY aggregate multiple supporting entities.

```text
Evidence A

supports

Decision

Evidence B

supports

Decision

↓

Decision

supported_by

{Evidence A, Evidence B}
```

Support aggregation SHALL preserve the identity of each supporting
entity.

---

# 19. Cross References

Related concepts:

- Evidence
- Observation
- Decision
- Policy
- Rule
- Metrics
- Knowledge

Related relationships:

- references
- derived_from
- inferred_from
- supported_by

Referenced specifications:

- Knowledge Architecture
- Reasoning Architecture
- Memory Architecture
- Knowledge Graph
- RFC-0269 Semantic Intelligence Layer

---

# 20. Summary

The **supports** relationship defines the canonical semantic association
between supporting evidence and the entities it justifies within the
SH-3 Ontology.

It establishes the semantic foundation for explainable AI, evidence
management, confidence assessment, decision justification, and
knowledge validation while preserving deterministic,
implementation-independent semantics.