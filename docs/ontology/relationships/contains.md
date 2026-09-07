# SH-3 Relationship: contains

Version: 1.0.0
Status: Stable
Category: Ontology Relationship
Relationship ID: REL-0001
Canonical Name: contains
Predicate: contains
Inverse Predicate: contained_by
Author: SH-3 Architecture Working Group

---

# 1. Overview

The **contains** relationship represents canonical semantic composition
between two ontology entities.

It indicates that a parent entity semantically includes one or more
child entities while preserving the independent identity of each child.

The relationship expresses structural organization rather than ownership.

---

# 2. Purpose

The contains relationship provides:

- Hierarchical organization
- Structural composition
- Semantic navigation
- Planning decomposition
- Knowledge graph construction
- Explainable reasoning

---

# 3. Canonical Definition

A subject **contains** an object when the object forms a semantic
component of the subject without losing its own semantic identity.

Containment does not imply ownership, execution, or dependency.

---

# 4. Characteristics

The **contains** relationship SHALL be:

- Directed
- Hierarchical
- Transitive
- Explainable
- Versioned
- Machine readable

It SHALL NOT imply exclusivity.

---

# 5. Relationship Signature

```
Subject

contains

Object
```

---

# 6. Semantic Meaning

The subject provides semantic structure.

The object contributes to the subject while remaining independently
identifiable.

Removing the object changes the composition of the subject but does not
invalidate the object's semantic definition.

---

# 7. Inverse Relationship

```
Object

contained_by

Subject
```

Inverse reasoning SHALL preserve semantic consistency.

---

# 8. Multiplicity

Supported cardinalities include:

- 1 → 1
- 1 → N
- N → N (when explicitly permitted)

Cardinality constraints SHALL be defined by the participating concepts.

---

# 9. Valid Examples

## Mission

```
Mission

contains

Goal
```

---

## Goal

```
Goal

contains

Task
```

---

## Knowledge Graph

```
KnowledgeBase

contains

Knowledge
```

---

## Federation

```
Federation

contains

Kernel
```

---

# 10. Invalid Examples

The following SHOULD NOT use **contains**:

```
Capability

contains

Runtime
```

Use **executed_by** instead.

---

```
Policy

contains

Mission
```

Use **governs** instead.

---

```
Task

contains

Capability
```

Use **uses** instead.

---

# 11. Reasoning Rules

Reasoning engines MAY infer:

```
A contains B

B contains C

↓

A contains C
```

Transitive inference SHALL be explicitly enabled by ontology rules.

---

# 12. Knowledge Graph Representation

Triple representation:

```
Mission

contains

Goal
```

Equivalent RDF form:

```
Mission
    sh3:contains
Goal
```

---

# 13. Registry Integration

The relationship SHALL reference:

- SEM Registry
- XRF Registry

Relationship metadata SHALL include:

- Relationship ID
- Predicate
- Version
- Provenance

---

# 14. Federation

Federated SH-3 systems SHALL preserve:

- Predicate identity
- Direction
- Semantic meaning
- Version compatibility

Relationship interpretation SHALL remain identical across all members.

---

# 15. Constraints

The **contains** relationship SHALL:

- Preserve object identity
- Preserve semantic hierarchy
- Remain implementation independent
- Support deterministic reasoning

It SHALL NOT imply:

- Ownership
- Execution
- Authorization
- Dependency

---

# 16. Examples

## Mission Structure

```text
Mission
 ├── Goal A
 ├── Goal B
 └── Goal C
```

Semantic triples:

```
Mission contains Goal A
Mission contains Goal B
Mission contains Goal C
```

---

## Planning Structure

```text
Goal
 ├── Task 1
 ├── Task 2
 └── Task 3
```

---

# 17. Cross References

Related concepts:

- Mission
- Goal
- Task
- Knowledge
- Federation

Related relationships:

- part_of
- belongs_to
- composed_of
- supports

Referenced specifications:

- Semantic Model
- Concepts
- Knowledge Graph
- RFC-0269 Semantic Intelligence Layer

---

# 18. Summary

The **contains** relationship defines canonical semantic composition
within the SH-3 Ontology.

It establishes hierarchical structure while preserving the independent
identity of contained entities, providing the foundation for semantic
navigation, reasoning, planning, and knowledge graph construction across
the SH-3 ecosystem.