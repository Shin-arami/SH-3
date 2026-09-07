# SH-3 Relationship: requires

Version: 1.0.0
Status: Stable
Category: Ontology Relationship
Relationship ID: REL-0202
Canonical Name: requires
Predicate: requires
Inverse Predicate: required_by
Author: SH-3 Architecture Working Group

---

# 1. Overview

The **requires** relationship represents a canonical semantic dependency
indicating that a subject cannot correctly fulfill its intended behavior
without the availability of another semantic entity.

Unlike **uses**, which represents actual runtime utilization,
**requires** represents a declared prerequisite.

The relationship defines dependency rather than execution.

---

# 2. Purpose

The requires relationship provides:

- Dependency declaration
- Capability requirements
- Service dependency modeling
- Runtime validation
- Dependency injection
- Capability resolution
- Federation compatibility

Every declared requirement SHALL be explicitly resolvable.

---

# 3. Canonical Definition

A subject **requires** an object when the object is a mandatory semantic
prerequisite for the subject to operate correctly.

A requirement SHALL exist independently of whether it is currently
satisfied.

---

# 4. Characteristics

The **requires** relationship SHALL be:

- Directed
- Declarative
- Deterministic
- Machine readable
- Explainable
- Versioned

The relationship SHALL represent necessity rather than utilization.

---

# 5. Relationship Signature

```text
Consumer

requires

Required Entity
```

---

# 6. Semantic Meaning

The subject declares that successful execution depends upon the
availability of the required entity.

Requirement declaration SHALL NOT imply immediate invocation or use.

---

# 7. Inverse Relationship

```text
Required Entity

required_by

Consumer
```

Both predicates SHALL represent identical dependency semantics.

---

# 8. Multiplicity

Supported cardinalities include:

- 1 → 1
- 1 → N
- N → N

Requirements MAY be mandatory or optional according to Policy.

---

# 9. Valid Examples

## Service Dependency

```text
PlannerService

requires

MemoryCapability
```

---

## Runtime Dependency

```text
Runtime

requires

SchedulerService
```

---

## Agent Dependency

```text
Agent

requires

ReasoningCapability
```

---

## Plugin Dependency

```text
OpenAIPlugin

requires

LLMProvider
```

---

## Mission Dependency

```text
Mission

requires

PlanningCapability
```

---

# 10. Invalid Examples

The following SHOULD NOT use **requires**.

```text
PlannerService

requires

PlannerService
```

Self-dependency SHALL NOT be declared.

---

```text
Runtime

requires

Kernel

(for execution)
```

Use **belongs_to** or **part_of** when describing architecture.

---

```text
Task

requires

Mission
```

Use **part_of**.

---

# 11. Dependency Resolution

Runtime SHALL resolve requirements before execution.

Resolution MAY consider:

- Capability
- Version
- Compatibility
- Policy
- Context
- Health
- Trust
- Availability

Unresolved mandatory requirements SHALL prevent execution.

---

# 12. Runtime Validation

Runtime SHALL validate:

- Requirement existence
- Version compatibility
- Semantic compatibility
- Policy compliance
- Trust constraints

Validation SHALL occur before execution begins.

---

# 13. Registry Integration

The requires relationship SHALL integrate with:

- CAP Registry
- MOD Registry
- SEM Registry
- XRF Registry

Metadata SHOULD include:

```yaml
consumer:
required_entity:
required_version:
compatibility:
mandatory:
```

---

# 14. Federation

Federated SH-3 systems MAY satisfy requirements using remote providers.

Federation SHALL preserve:

- Requirement semantics
- Compatibility
- Version
- Trust
- Provenance

Requirement resolution SHALL remain deterministic.

---

# 15. Constraints

The **requires** relationship SHALL:

- Declare prerequisites
- Preserve semantic identity
- Support dependency resolution
- Remain implementation independent

The relationship SHALL NOT imply:

- Ownership
- Execution
- Invocation
- Scheduling
- Structural composition

---

# 16. Relationship Comparison

| Relationship | Meaning |
|--------------|---------|
| provides | Makes an entity available |
| requires | Declares a prerequisite |
| uses | Performs runtime utilization |
| implements | Realizes a semantic contract |
| executes | Performs execution |

---

# 17. Examples

## Dependency Injection

```text
PlannerService

requires

MemoryCapability

↓

Runtime Resolver

↓

MemoryService
```

---

## Capability Resolution

```text
Agent

↓

requires

PlanningCapability

↓

Capability Registry

↓

PlannerService
```

---

## Federation Resolution

```text
Local Runtime

↓

requires

TranslationCapability

↓

Remote Federation Provider
```

---

# 18. Reasoning Rules

Reasoning engines MAY infer:

```text
PlannerService

requires

PlanningCapability

PlanningCapability

provided_by

PlannerProvider

↓

PlannerService

can_be_satisfied_by

PlannerProvider
```

Inference SHALL preserve Policy constraints.

---

# 19. Cross References

Related concepts:

- Capability
- Service
- Runtime
- Kernel
- Agent
- Mission

Related relationships:

- provides
- uses
- implements
- executes
- required_by

Referenced specifications:

- CAP Registry
- MOD Registry
- Service Discovery
- Dependency Injection
- Plugin API
- SDK
- RFC-0261 SH-3 Architecture Framework

---

# 20. Summary

The **requires** relationship defines the canonical semantic dependency
between a consumer and the capabilities, services, resources, or
interfaces it depends upon within the SH-3 Ontology.

It establishes the foundation for dependency declaration, runtime
validation, capability resolution, dependency injection, and federated
resource discovery while preserving deterministic behavior and semantic
interoperability.