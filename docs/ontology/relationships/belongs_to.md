# SH-3 Relationship: belongs_to

Version: 1.0.0
Status: Stable
Category: Ontology Relationship
Relationship ID: REL-0002
Canonical Name: belongs_to
Predicate: belongs_to
Inverse Predicate: owns
Author: SH-3 Architecture Working Group

---

# 1. Overview

The **belongs_to** relationship represents canonical semantic
membership, ownership, administration, or governance between ontology
entities.

It indicates that a subject is associated with, managed by, or is a
member of another entity without implying structural composition.

Unlike **contains**, **belongs_to** expresses affiliation rather than
hierarchical decomposition.

---

# 2. Purpose

The belongs_to relationship provides:

- Membership
- Ownership
- Administrative assignment
- Organizational grouping
- Governance relationships
- Semantic navigation

---

# 3. Canonical Definition

A subject **belongs_to** an object when the object represents the
administrative, organizational, or ownership context of the subject.

The subject preserves its own identity while existing within the
governance or ownership domain of the object.

---

# 4. Characteristics

The **belongs_to** relationship SHALL be:

- Directed
- Explainable
- Versioned
- Machine readable
- Non-transitive
- Context-aware

The relationship SHALL NOT imply structural containment.

---

# 5. Relationship Signature

```
Subject

belongs_to

Object
```

---

# 6. Semantic Meaning

The object provides governance, ownership, or membership context.

The subject remains an independent semantic entity.

The relationship describes administrative association rather than
physical or logical composition.

---

# 7. Inverse Relationship

```
Object

owns

Subject
```

Inverse reasoning SHALL preserve semantic consistency.

---

# 8. Multiplicity

Supported cardinalities include:

- 1 → 1
- N → 1
- N → N (when explicitly defined)

Multiplicity SHALL be constrained by participating concepts.

---

# 9. Valid Examples

## Service Assignment

```
Service

belongs_to

Runtime
```

---

## Runtime Administration

```
Runtime

belongs_to

Kernel
```

---

## Agent Membership

```
Agent

belongs_to

Federation
```

---

## Knowledge Ownership

```
Knowledge

belongs_to

Memory
```

---

# 10. Invalid Examples

The following SHOULD NOT use **belongs_to**.

```
Mission

belongs_to

Goal
```

Use **contains**.

---

```
Task

belongs_to

Capability
```

Use **uses**.

---

```
Policy

belongs_to

Mission
```

Use **governs**.

---

# 11. Reasoning Rules

Reasoning engines SHALL infer ownership context only.

Example:

```
Runtime

belongs_to

Kernel

↓

Runtime managed by Kernel
```

Ownership SHALL NOT imply execution or dependency.

---

# 12. Knowledge Graph Representation

Triple representation:

```
Agent

belongs_to

Federation
```

Equivalent RDF form:

```
Agent
    sh3:belongs_to
Federation
```

---

# 13. Registry Integration

Relationship metadata SHALL include:

- Relationship ID
- Predicate
- Version
- Provenance

Relationship identifiers SHALL remain globally unique.

---

# 14. Federation

Federation members SHALL preserve:

- Predicate identity
- Administrative meaning
- Direction
- Version

Membership semantics SHALL remain consistent across all nodes.

---

# 15. Constraints

The **belongs_to** relationship SHALL:

- Preserve subject identity
- Preserve governance semantics
- Remain implementation independent
- Support deterministic interpretation

The relationship SHALL NOT imply:

- Structural composition
- Execution
- Capability realization
- Data dependency

---

# 16. Examples

## Runtime Ownership

```text
Kernel
 ├── Runtime A
 ├── Runtime B
 └── Runtime C
```

Semantic triples:

```
Runtime A belongs_to Kernel
Runtime B belongs_to Kernel
Runtime C belongs_to Kernel
```

---

## Federation Membership

```text
Federation
 ├── Agent Alpha
 ├── Agent Beta
 └── Agent Gamma
```

Semantic triples:

```
Agent Alpha belongs_to Federation
Agent Beta belongs_to Federation
Agent Gamma belongs_to Federation
```

---

# 17. Cross References

Related concepts:

- Runtime
- Kernel
- Agent
- Federation
- Memory
- Knowledge

Related relationships:

- contains
- part_of
- governed_by
- managed_by
- owns

Referenced specifications:

- Concepts
- Semantic Model
- Knowledge Graph
- RFC-0264 Meta Governance Architecture
- RFC-0269 Semantic Intelligence Layer

---

# 18. Summary

The **belongs_to** relationship defines canonical semantic membership,
ownership, and governance within the SH-3 Ontology.

It provides a deterministic and implementation-independent mechanism for
expressing administrative association while preserving the independent
identity of participating entities.

Together with **contains**, **belongs_to** forms one of the fundamental
structural relationships underpinning the SH-3 semantic graph.