# SH-3 Relationship: part_of

Version: 1.0.0
Status: Stable
Category: Ontology Relationship
Relationship ID: REL-0003
Canonical Name: part_of
Predicate: part_of
Inverse Predicate: contains
Author: SH-3 Architecture Working Group

---

# 1. Overview

The **part_of** relationship represents canonical structural inclusion
within the SH-3 Ontology.

It indicates that a subject is a semantic component of a larger object
while preserving its own identity.

Unlike **belongs_to**, **part_of** expresses composition rather than
administrative affiliation.

---

# 2. Purpose

The part_of relationship provides:

- Structural decomposition
- Hierarchical modeling
- Semantic composition
- Knowledge graph navigation
- Architecture modeling
- Explainable reasoning

---

# 3. Canonical Definition

A subject is **part_of** an object when the subject contributes to the
semantic structure of the object.

The object remains meaningful without changing the semantic identity of
the subject.

---

# 4. Characteristics

The **part_of** relationship SHALL be:

- Directed
- Hierarchical
- Transitive
- Explainable
- Machine readable
- Versioned

It SHALL represent structural composition only.

---

# 5. Relationship Signature

```
Subject

part_of

Object
```

---

# 6. Semantic Meaning

The subject contributes to the composition of the object.

The object is semantically composed from one or more parts.

Structural inclusion SHALL NOT imply execution, ownership, or policy.

---

# 7. Inverse Relationship

```
Object

contains

Subject
```

Both predicates SHALL represent identical semantic composition from
opposite directions.

---

# 8. Multiplicity

Supported cardinalities include:

- 1 → 1
- N → 1
- N → N (when explicitly defined)

Cardinality SHALL be determined by the participating concepts.

---

# 9. Valid Examples

## Goal

```
Goal

part_of

Mission
```

---

## Task

```
Task

part_of

Goal
```

---

## Runtime

```
Runtime

part_of

Kernel
```

---

## Kernel

```
Kernel

part_of

Federation
```

---

# 10. Invalid Examples

The following SHOULD NOT use **part_of**.

```
Capability

part_of

Service
```

Use **implemented_by**.

---

```
Knowledge

part_of

Policy
```

Use **governed_by**.

---

```
Service

part_of

Runtime
```

Use **executed_by** if execution is intended.

---

# 11. Reasoning Rules

Reasoning engines MAY infer transitive structure.

```
Task

part_of

Goal

Goal

part_of

Mission

↓

Task

part_of

Mission
```

Transitive reasoning SHALL preserve semantic consistency.

---

# 12. Knowledge Graph Representation

Triple representation:

```
Task

part_of

Goal
```

Equivalent RDF form:

```
Task
    sh3:part_of
Goal
```

---

# 13. Registry Integration

Relationship metadata SHALL include:

- Relationship ID
- Predicate
- Version
- Provenance

The relationship SHALL be registered in the SEM Registry.

---

# 14. Federation

Federated systems SHALL preserve:

- Predicate identity
- Structural semantics
- Version compatibility
- Direction

Structural interpretation SHALL remain deterministic.

---

# 15. Constraints

The **part_of** relationship SHALL:

- Preserve semantic identity
- Preserve hierarchy
- Support deterministic reasoning
- Remain implementation independent

It SHALL NOT imply:

- Ownership
- Authorization
- Execution
- Dependency

---

# 16. Examples

## Mission Hierarchy

```text
Mission
 ├── Goal A
 │     ├── Task 1
 │     └── Task 2
 └── Goal B
```

Semantic triples:

```
Goal A part_of Mission
Task 1 part_of Goal A
Task 2 part_of Goal A
Goal B part_of Mission
```

---

## Federation Structure

```text
Federation
 ├── Kernel A
 ├── Kernel B
 └── Kernel C
```

Semantic triples:

```
Kernel A part_of Federation
Kernel B part_of Federation
Kernel C part_of Federation
```

---

# 17. Cross References

Related concepts:

- Mission
- Goal
- Task
- Runtime
- Kernel
- Federation

Related relationships:

- contains
- belongs_to
- composed_of
- supports

Referenced specifications:

- Concepts
- Semantic Model
- Knowledge Graph
- RFC-0261 SH-3 Architecture Framework
- RFC-0269 Semantic Intelligence Layer

---

# 18. Summary

The **part_of** relationship defines canonical structural inclusion
within the SH-3 Ontology.

It provides the inverse perspective of **contains**, enabling semantic
decomposition, hierarchical reasoning, and deterministic knowledge graph
construction while preserving the independent identity of participating
concepts.