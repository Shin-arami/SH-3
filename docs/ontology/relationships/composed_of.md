# SH-3 Relationship: composed_of

Version: 1.0.0
Status: Stable
Category: Ontology Relationship
Relationship ID: REL-0004
Canonical Name: composed_of
Predicate: composed_of
Inverse Predicate: component_of
Author: SH-3 Architecture Working Group

---

# 1. Overview

The **composed_of** relationship represents canonical semantic
composition between an aggregate entity and the components from which it
is formed.

Unlike **contains**, which expresses hierarchical inclusion,
**composed_of** expresses intrinsic structural composition.

The composed entity derives its structure from its components while each
component preserves its own semantic identity.

---

# 2. Purpose

The composed_of relationship provides:

- Structural composition
- Aggregate modeling
- Architecture representation
- Component decomposition
- Knowledge graph construction
- Explainable reasoning

---

# 3. Canonical Definition

A subject is **composed_of** one or more objects when the objects are
essential structural components that collectively define the subject.

Composition describes structural construction rather than execution,
ownership, or dependency.

---

# 4. Characteristics

The **composed_of** relationship SHALL be:

- Directed
- Structural
- Explainable
- Machine readable
- Versioned
- Deterministic

It MAY be transitive when explicitly defined by ontology rules.

---

# 5. Relationship Signature

```
Subject

composed_of

Component
```

---

# 6. Semantic Meaning

The subject is structurally constructed from one or more components.

Components retain independent semantic identity while contributing to
the aggregate structure.

Composition SHALL NOT imply execution or governance.

---

# 7. Inverse Relationship

```
Component

component_of

Subject
```

Inverse reasoning SHALL preserve semantic equivalence.

---

# 8. Multiplicity

Supported cardinalities include:

- 1 → 1
- 1 → N
- N → N (explicitly defined only)

Multiplicity SHALL be constrained by the participating concepts.

---

# 9. Valid Examples

## Kernel

```
Kernel

composed_of

Runtime
```

---

## Runtime

```
Runtime

composed_of

Service
```

---

## Mission

```
Mission

composed_of

Goal
```

---

## Goal

```
Goal

composed_of

Task
```

---

# 10. Invalid Examples

The following SHOULD NOT use **composed_of**.

```
Task

composed_of

Capability
```

Use **uses**.

---

```
Agent

composed_of

Knowledge
```

Use **uses**.

---

```
Policy

composed_of

Mission
```

Use **governs**.

---

# 11. Reasoning Rules

Reasoning engines MAY infer structural composition.

```
Kernel

composed_of

Runtime

Runtime

composed_of

Service

↓

Kernel

indirectly composed_of

Service
```

Indirect composition SHALL be distinguishable from direct composition.

---

# 12. Knowledge Graph Representation

Triple representation:

```
Kernel

composed_of

Runtime
```

Equivalent RDF form:

```
Kernel
    sh3:composed_of
Runtime
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
- Composition semantics
- Version compatibility
- Structural integrity

Composition SHALL remain deterministic across Federation members.

---

# 15. Constraints

The **composed_of** relationship SHALL:

- Preserve component identity
- Preserve aggregate semantics
- Support deterministic reasoning
- Remain implementation independent

It SHALL NOT imply:

- Ownership
- Authorization
- Execution
- Scheduling

---

# 16. Examples

## Runtime Architecture

```text
Runtime
 ├── EventBus
 ├── Scheduler
 ├── ResourceManager
 └── Pipeline
```

Semantic triples:

```
Runtime composed_of EventBus
Runtime composed_of Scheduler
Runtime composed_of ResourceManager
Runtime composed_of Pipeline
```

---

## Kernel Architecture

```text
Kernel
 ├── Runtime Registry
 ├── Mission Manager
 ├── Policy Manager
 └── Event Router
```

Semantic triples:

```
Kernel composed_of Runtime Registry
Kernel composed_of Mission Manager
Kernel composed_of Policy Manager
Kernel composed_of Event Router
```

---

# 17. Cross References

Related concepts:

- Kernel
- Runtime
- Service
- Mission
- Goal
- Task

Related relationships:

- contains
- part_of
- belongs_to
- implements

Referenced specifications:

- Concepts
- Semantic Model
- Knowledge Graph
- RFC-0261 SH-3 Architecture Framework

---

# 18. Summary

The **composed_of** relationship defines canonical structural
composition within the SH-3 Ontology.

It expresses how aggregate entities are formed from constituent
components while preserving semantic identity, enabling deterministic
architecture modeling, semantic reasoning, and implementation-
independent knowledge graph construction throughout the SH-3 ecosystem.