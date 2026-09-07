# SH-3 Relationship: provides

Version: 1.0.0
Status: Stable
Category: Ontology Relationship
Relationship ID: REL-0201
Canonical Name: provides
Predicate: provides
Inverse Predicate: provided_by
Author: SH-3 Architecture Working Group

---

# 1. Overview

The **provides** relationship represents the canonical semantic
association between a provider entity and a capability, service,
resource, interface, or function that it makes available.

Unlike **implements**, which describes semantic realization,
**provides** describes semantic availability.

The relationship defines what an entity exposes to consumers.

---

# 2. Purpose

The provides relationship enables:

- Capability publication
- Service discovery
- Interface exposure
- Resource advertisement
- Dependency resolution
- Registry integration
- Runtime discovery
- Federation interoperability

Every provided entity SHALL be discoverable through its provider.

---

# 3. Canonical Definition

A subject **provides** an object when the subject makes the object
available for discovery, selection, access, or use by other entities.

Providing an entity SHALL NOT imply ownership, execution, or exclusive
access.

---

# 4. Characteristics

The **provides** relationship SHALL be:

- Directed
- Discoverable
- Observable
- Explainable
- Machine readable
- Versioned
- Deterministic

The relationship SHALL preserve provider independence.

---

# 5. Relationship Signature

```text
Provider

provides

Provided Entity
```

---

# 6. Semantic Meaning

The provider advertises one or more semantic entities for external
consumption.

The provided entity retains its canonical semantic identity.

Consumers interact with the provided entity rather than the provider's
internal implementation.

---

# 7. Inverse Relationship

```text
Provided Entity

provided_by

Provider
```

The inverse relationship SHALL preserve identical semantics.

---

# 8. Multiplicity

Supported cardinalities include:

- 1 → 1
- 1 → N
- N → N

Multiple providers MAY expose the same semantic capability.

Selection SHALL be determined by Runtime, Policy, or Context.

---

# 9. Valid Examples

## Service

```text
PlannerService

provides

PlanningCapability
```

---

## Runtime

```text
Runtime

provides

ExecutionEnvironment
```

---

## Kernel

```text
Kernel

provides

CoordinationService
```

---

## Plugin

```text
OpenAIPlugin

provides

LLMCapability
```

---

## Memory

```text
MemoryService

provides

KnowledgeStore
```

---

# 10. Invalid Examples

The following SHOULD NOT use **provides**.

```text
PlannerService

provides

Runtime
```

Use **executed_by**.

---

```text
Mission

provides

Goal
```

Use **contains**.

---

```text
Capability

provides

Implementation
```

Use **implemented_by**.

---

# 11. Discovery Semantics

A provider SHALL publish sufficient metadata for discovery.

Discovery metadata MAY include:

- Identifier
- Name
- Version
- Interface
- Capability
- Compatibility
- Trust Level
- Availability

Discovery SHALL be deterministic.

---

# 12. Runtime Resolution

Runtime MAY resolve providers using:

- Capability
- Context
- Policy
- Version
- Cost
- Priority
- Health
- Trust

Provider selection SHALL be reproducible.

---

# 13. Registry Integration

The provides relationship SHALL integrate with:

- CAP Registry
- MOD Registry
- SEM Registry
- XRF Registry

Registry metadata SHALL include:

```yaml
provider:
provided_entity:
version:
compatibility:
status:
```

---

# 14. Federation

Federated SH-3 systems SHALL exchange provider metadata.

Federation SHALL preserve:

- Provider identity
- Capability identity
- Semantic compatibility
- Trust metadata
- Version information

Federated discovery SHALL remain deterministic.

---

# 15. Constraints

The **provides** relationship SHALL:

- Preserve semantic identity
- Support multiple providers
- Remain implementation independent
- Support runtime discovery
- Support capability negotiation

The relationship SHALL NOT imply:

- Ownership
- Execution
- Scheduling
- Structural composition
- Dependency

---

# 16. Relationship Comparison

| Relationship | Meaning |
|--------------|---------|
| implements | Realizes semantic behavior |
| provides | Makes a semantic entity available |
| requires | Declares a required dependency |
| uses | Performs actual utilization |
| executes | Performs execution |

---

# 17. Examples

## Capability Registry

```text
PlannerService
    provides
PlanningCapability

MemoryService
    provides
MemoryCapability

LearningService
    provides
LearningCapability
```

---

## Plugin Discovery

```text
Plugin Registry

↓

Planner Plugin

↓

provides

Planning Capability
```

---

## Runtime Resolution

```text
Capability Request

↓

Capability Registry

↓

Provider Discovery

↓

PlannerService

↓

Execution
```

---

# 18. Reasoning Rules

Reasoning engines MAY infer:

```text
Service

implements

PlanningCapability

↓

Service

provides

PlanningCapability
```

when implementation visibility is explicitly configured.

Automatic inference SHALL be governed by Policy.

---

# 19. Cross References

Related concepts:

- Capability
- Service
- Runtime
- Kernel
- Plugin
- Memory

Related relationships:

- implements
- requires
- uses
- executes
- provided_by

Referenced specifications:

- CAP Registry
- MOD Registry
- Plugin API
- Extension API
- SDK
- Service Discovery
- Dependency Injection
- RFC-0261 SH-3 Architecture Framework

---

# 20. Summary

The **provides** relationship defines the canonical semantic association
between a provider and the capabilities, services, resources, or
interfaces that it exposes within the SH-3 Ontology.

It establishes the semantic foundation for capability discovery,
service registration, runtime resolution, plugin interoperability,
dependency management, and federated resource advertisement while
preserving deterministic behavior and implementation-independent
architecture.