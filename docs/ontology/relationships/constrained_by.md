# SH-3 Relationship: constrained_by

Version: 1.0.0
Status: Stable
Category: Ontology Relationship
Relationship ID: REL-0503
Canonical Name: constrained_by
Predicate: constrained_by
Inverse Predicate: constrains
Author: SH-3 Architecture Working Group

---

# 1. Overview

The **constrained_by** relationship represents the canonical semantic
association in which an entity is limited, bounded, or restricted by
another entity.

Constraints define acceptable operational boundaries without defining
ownership, permission, or governance authority.

Unlike **authorized_by**, which grants permission,
**constrained_by** defines restrictions.

---

# 2. Purpose

The constrained_by relationship enables:

- Safety boundaries
- Resource limitations
- Operational restrictions
- Runtime protection
- AI alignment constraints
- Security boundaries
- Compliance requirements
- Optimization limits

Every autonomous entity SHALL operate within defined constraints.

---

# 3. Canonical Definition

A subject **constrained_by** an object when the object defines limits,
conditions, boundaries, or restrictions that the subject SHALL respect.

Constraints MAY restrict behavior, resources, time, scope, or outcomes.

---

# 4. Characteristics

The **constrained_by** relationship SHALL be:

- Directed
- Normative
- Deterministic
- Auditable
- Machine readable
- Versioned

Constraints SHALL remain explicitly identifiable.

---

# 5. Relationship Signature

```text
Constrained Entity

constrained_by

Constraint Entity
```

---

# 6. Semantic Meaning

The constraint entity defines the acceptable operational boundary of the
constrained entity.

Constraints MAY include:

- Safety limits
- Resource limits
- Rate limits
- Time limits
- Scope restrictions
- Compliance requirements
- Optimization boundaries
- Ethical restrictions

Constraints SHALL NOT imply permission.

---

# 7. Inverse Relationship

```text
Constraint Entity

constrains

Constrained Entity
```

The inverse relationship SHALL preserve constraint semantics.

---

# 8. Multiplicity

Supported cardinalities include:

- 1 → 1
- 1 → N
- N → N

Multiple constraints MAY apply simultaneously.

---

# 9. Valid Examples

## Agent Safety

```text
Agent

constrained_by

SafetyConstraint
```

---

## Runtime Resource

```text
Runtime

constrained_by

ResourceLimit
```

---

## Tool Execution

```text
Tool

constrained_by

ExecutionBoundary
```

---

## Mission

```text
Mission

constrained_by

MissionScope
```

---

## Optimization

```text
Optimizer

constrained_by

PerformanceConstraint
```

---

# 10. Invalid Examples

The following SHOULD NOT use **constrained_by**.

```text
Agent

constrained_by

PermissionPolicy
```

Use **authorized_by**.

---

```text
Runtime

constrained_by

Kernel
```

Use structural relationships.

---

```text
Service

constrained_by

MemoryService
```

Use **requires** or **uses**.

---

# 11. Constraint Semantics

Constraints MAY define:

- Minimum values
- Maximum values
- Allowed states
- Forbidden states
- Invariants
- Thresholds
- Budgets
- Deadlines

Constraint evaluation SHALL be deterministic.

---

# 12. Runtime Enforcement

Runtime MAY enforce constraints during:

- Planning
- Scheduling
- Execution
- Resource allocation
- Learning
- Optimization
- Recovery

Constraint violations SHOULD generate Events.

Example:

```text
ConstraintViolationEvent
```

---

# 13. Registry Integration

The constrained_by relationship SHALL integrate with:

- POL Registry
- SEC Registry
- CAP Registry
- EVT Registry
- XRF Registry

Metadata MAY include:

```yaml
constrained_entity:
constraint:
type:
threshold:
scope:
severity:
policy_version:
```

---

# 14. Federation

Federated SH-3 systems SHALL preserve:

- Constraint identity
- Scope
- Version
- Enforcement authority
- Audit information

Cross-domain constraints SHALL remain explicit.

---

# 15. Constraints

The **constrained_by** relationship SHALL:

- Preserve operational boundaries
- Support safety enforcement
- Support compliance
- Support explainability
- Remain implementation independent

The relationship SHALL NOT imply:

- Permission
- Ownership
- Governance authority
- Execution

---

# 16. Relationship Comparison

| Relationship | Meaning |
|--------------|---------|
| governed_by | Controlled by governance |
| authorized_by | Granted permission |
| constrained_by | Limited by boundaries |
| requires | Declared dependency |
| uses | Runtime utilization |

---

# 17. Examples

## Autonomous Agent

```text
Agent

governed_by

AgentPolicy

authorized_by

CapabilityPermission

constrained_by

SafetyConstraint
```

---

## Runtime

```text
Runtime

governed_by

ExecutionPolicy

authorized_by

ExecutionPermission

constrained_by

ResourceLimit
```

---

## Optimization Loop

```text
Optimizer

constrained_by

PerformanceBoundary

↓

Optimizer

executes

OptimizationTask
```

---

# 18. Reasoning Rules

Reasoning engines MAY detect constraint inheritance.

```text
Agent

constrained_by

SafetyConstraint

SafetyConstraint

applies_to

ToolExecution

↓

Agent

constrained_by

ToolExecutionConstraint
```

Inherited constraints SHALL remain distinguishable from direct
constraints.

---

# 19. Cross References

Related concepts:

- Constraint
- Policy
- Safety
- Security
- Runtime
- Agent
- Optimization

Related relationships:

- governed_by
- authorized_by
- requires
- executes
- constrains

Referenced specifications:

- Safety Architecture
- Policy Architecture
- Security Architecture
- Autonomous Governance Architecture
- RFC-0264 Meta Governance Architecture

---

# 20. Summary

The **constrained_by** relationship defines the canonical semantic
association between an entity and the boundaries that restrict its
operation within the SH-3 Ontology.

It establishes the foundation for AI safety, runtime protection,
resource management, compliance enforcement, optimization boundaries,
and autonomous system control while preserving deterministic,
auditable, and implementation-independent governance semantics.