# SH-3 Relationship: derived_from

Version: 1.0.0
Status: Stable
Category: Ontology Relationship
Relationship ID: REL-0401
Canonical Name: derived_from
Predicate: derived_from
Inverse Predicate: source_of
Author: SH-3 Architecture Working Group

---

# 1. Overview

The **derived_from** relationship represents the canonical semantic
association between a derived entity and the source entity from which it
originated.

It provides explicit provenance for knowledge, decisions, artifacts,
plans, models, and other semantic entities.

Unlike **inferred_from**, which represents logical inference,
**derived_from** represents traceable origin.

---

# 2. Purpose

The derived_from relationship enables:

- Knowledge provenance
- Artifact lineage
- Traceability
- Learning history
- Explainable AI
- Knowledge graph construction
- Version evolution
- Auditability

Every derived entity SHALL reference one or more identifiable sources.

---

# 3. Canonical Definition

A subject **derived_from** an object when the subject originates from,
is transformed from, or is produced using the object.

The derivation MAY involve transformation, aggregation, filtering,
summarization, refinement, or synthesis.

---

# 4. Characteristics

The **derived_from** relationship SHALL be:

- Directed
- Explainable
- Traceable
- Machine readable
- Versioned
- Deterministic

Derivation SHALL preserve provenance.

---

# 5. Relationship Signature

```text
Derived Entity

derived_from

Source Entity
```

---

# 6. Semantic Meaning

The source contributes semantic content to the derived entity.

The derived entity SHALL preserve a traceable relationship to its
origin.

Derivation SHALL NOT imply logical proof.

---

# 7. Inverse Relationship

```text
Source Entity

source_of

Derived Entity
```

The inverse relationship SHALL preserve provenance semantics.

---

# 8. Multiplicity

Supported cardinalities include:

- 1 → 1
- N → 1
- N → N

A derived entity MAY have multiple independent sources.

---

# 9. Valid Examples

## Knowledge

```text
Summary

derived_from

KnowledgeDocument
```

---

## AI Learning

```text
PolicyModel

derived_from

TrainingDataset
```

---

## Planning

```text
ExecutionPlan

derived_from

Mission
```

---

## Memory

```text
SemanticMemory

derived_from

Episode
```

---

## Ontology

```text
ConceptEmbedding

derived_from

Concept
```

---

# 10. Invalid Examples

The following SHOULD NOT use **derived_from**.

```text
PlannerService

derived_from

MemoryService
```

Use **uses**.

---

```text
Mission

derived_from

Goal
```

Use **contains**.

---

```text
Runtime

derived_from

Kernel
```

Use **part_of**.

---

# 11. Provenance Semantics

Derivation SHOULD preserve:

- Source identifier
- Version
- Timestamp
- Transformation process
- Author
- Confidence
- Provenance chain

Every derivation SHALL remain explainable.

---

# 12. Transformation Semantics

Transformation MAY include:

- Normalization
- Aggregation
- Compression
- Translation
- Optimization
- Summarization
- Learning
- Adaptation

Transformation SHALL preserve provenance.

---

# 13. Registry Integration

The derived_from relationship SHALL integrate with:

- KG Registry
- MEM Registry
- SEM Registry
- XRF Registry

Metadata MAY include:

```yaml
derived_entity:
source_entity:
version:
timestamp:
transformation:
confidence:
```

---

# 14. Federation

Federated SH-3 systems SHALL preserve provenance across node
boundaries.

Federation SHALL preserve:

- Source identity
- Provenance chain
- Version
- Trust
- Traceability

---

# 15. Constraints

The **derived_from** relationship SHALL:

- Preserve provenance
- Support explainability
- Support reproducibility
- Support auditing
- Remain implementation independent

The relationship SHALL NOT imply:

- Execution
- Ownership
- Structural composition
- Logical inference

---

# 16. Relationship Comparison

| Relationship | Meaning |
|--------------|---------|
| derived_from | Origin or transformation |
| inferred_from | Logical reasoning |
| references | Citation or linkage |
| supports | Supporting evidence |

---

# 17. Examples

## Learning Pipeline

```text
Dataset

↓

Training

↓

PolicyModel

derived_from

Dataset
```

---

## Knowledge Refinement

```text
Document

↓

Summarizer

↓

Summary

derived_from

Document
```

---

## Memory Consolidation

```text
Episode

↓

Consolidation

↓

SemanticMemory

derived_from

Episode
```

---

# 18. Reasoning Rules

Reasoning engines MAY infer provenance chains.

```text
Summary

derived_from

Document

Document

derived_from

Dataset

↓

Summary

indirectly_derived_from

Dataset
```

Indirect derivation SHALL remain distinguishable from direct derivation.

---

# 19. Cross References

Related concepts:

- Knowledge
- Memory
- Dataset
- Document
- Mission
- Policy
- Model

Related relationships:

- inferred_from
- references
- supports
- source_of

Referenced specifications:

- Knowledge Architecture
- Memory Architecture
- Learning Architecture
- Knowledge Graph
- RFC-0269 Semantic Intelligence Layer

---

# 20. Summary

The **derived_from** relationship defines the canonical semantic
association between a derived entity and its source within the SH-3
Ontology.

It establishes the foundation for provenance, explainability,
traceability, knowledge evolution, learning systems, and semantic
auditing while preserving deterministic and implementation-independent
knowledge management.