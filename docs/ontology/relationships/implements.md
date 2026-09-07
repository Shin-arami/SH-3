# SH-3 Relationship: implements

Version: 1.0.0
Status: Stable
Category: Ontology Relationship
Relationship ID: REL-0101
Canonical Name: implements
Predicate: implements
Inverse Predicate: implemented_by
Author: SH-3 Architecture Working Group

---

# 1. Overview

The **implements** relationship represents the canonical semantic link
between an implementation entity and an abstract semantic definition.

It declares that an implementation realizes the behavior specified by a
Capability, Interface, Protocol, or Contract without changing its
canonical semantics.

The relationship separates **what** a system provides from **how** it is
implemented.

---

# 2. Purpose

The implements relationship provides:

- Capability realization
- Interface implementation
- Semantic abstraction
- Replaceable implementations
- Service discovery
- Dependency inversion
- Runtime substitution

Every implementation SHALL preserve the semantic definition of the
entity it implements.

---

# 3. Canonical Definition

A subject **implements** an object when the subject provides a complete
and semantically compatible realization of the behavior defined by the
object.

The implementation MAY differ internally.

The observable semantics SHALL remain equivalent.

---

# 4. Characteristics

The **implements** relationship SHALL be:

- Directed
- Semantic
- Replaceable
- Deterministic
- Machine readable
- Versioned

It SHALL preserve behavioral compatibility.

---

# 5. Relationship Signature

```
Implementation

implements

Capability
```

---

# 6. Semantic Meaning

The implementation fulfills the contract defined by the abstract entity.

Consumers depend upon the semantic contract rather than the concrete
implementation.

---

# 7. Inverse Relationship

```
Capability

implemented_by

Implementation
```

Both predicates SHALL express identical semantics from opposite
directions.

---

# 8. Multiplicity

Supported cardinalities include:

- 1 → 1
- N → 1
- N → N (multiple compatible implementations)

Multiple implementations MAY coexist.

Selection SHALL be determined by Runtime or Policy.

---

# 9. Valid Examples

## Service

```
PlannerService

implements

PlanningCapability
```

---

## Plugin

```
OpenAIPlugin

implements

LLMCapability
```

---

## Runtime Component

```
PriorityScheduler

implements

SchedulerInterface
```

---

## Kernel Component

```
RegistryManager

implements

RegistryCapability
```

---

# 10. Invalid Examples

The following SHOULD NOT use **implements**.

```
Runtime

implements

Kernel
```

Use **belongs_to** or **part_of**.

---

```
Mission

implements

Goal
```

Use **contains**.

---

```
Knowledge

implements

Policy
```

Use **governed_by**.

---

# 11. Behavioral Compatibility

Every implementation SHALL preserve:

- Input semantics
- Output semantics
- Error semantics
- Policy compliance
- Observable behavior

Internal optimization SHALL NOT alter semantic meaning.

---

# 12. Runtime Resolution

Runtime MAY select an implementation using:

- Policy
- Context
- Version
- Cost
- Performance
- Trust

Selection SHALL remain deterministic.

---

# 13. Knowledge Graph Representation

Triple representation:

```
PlannerService

implements

PlanningCapability
```

Equivalent RDF form:

```
PlannerService
    sh3:implements
PlanningCapability
```

---

# 14. Registry Integration

The relationship SHALL integrate with:

- CAP Registry
- MOD Registry
- SEM Registry

Metadata SHALL include:

- Capability ID
- Implementation ID
- Compatibility Version
- Provenance

---

# 15. Federation

Federated systems SHALL preserve:

- Predicate identity
- Capability semantics
- Compatibility metadata
- Version mapping

Equivalent implementations MAY differ internally while preserving
canonical semantics.

---

# 16. Constraints

The **implements** relationship SHALL:

- Preserve semantic contracts
- Support multiple implementations
- Remain implementation independent
- Support runtime substitution

It SHALL NOT imply:

- Ownership
- Execution
- Scheduling
- Structural composition

---

# 17. Examples

## Capability Registry

```text
PlanningCapability
 ├── PlannerService
 ├── AIPlanner
 └── DistributedPlanner
```

Semantic triples:

```
PlannerService implements PlanningCapability
AIPlanner implements PlanningCapability
DistributedPlanner implements PlanningCapability
```

---

## Runtime Resolution

```text
PlanningCapability

↓

Runtime Resolver

↓

PlannerService
```

---

# 18. Cross References

Related concepts:

- Capability
- Service
- Runtime
- Kernel
- Plugin

Related relationships:

- provides
- executes
- uses
- requires
- implemented_by

Referenced specifications:

- CAP Registry
- MOD Registry
- Plugin API
- Extension API
- SDK
- RFC-0261 SH-3 Architecture Framework

---

# 19. Summary

The **implements** relationship defines the canonical connection between
abstract semantic definitions and their concrete implementations within
the SH-3 Ontology.

It enables semantic abstraction, implementation replacement, runtime
resolution, plugin interoperability, and capability discovery while
preserving deterministic behavior and implementation-independent
architecture.