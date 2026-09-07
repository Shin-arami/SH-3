# SH-3 Relationship: governed_by

Version: 1.0.0
Status: Stable
Category: Ontology Relationship
Relationship ID: REL-0501
Canonical Name: governed_by
Predicate: governed_by
Inverse Predicate: governs
Author: SH-3 Architecture Working Group

---

# 1. Overview

The **governed_by** relationship represents the canonical semantic
association in which an entity operates under the authority, policies,
rules, or governance framework of another entity.

Governance defines normative constraints rather than structural,
behavioral, or dependency relationships.

Unlike **authorized_by**, which grants permission,
**governed_by** establishes the governing framework.

---

# 2. Purpose

The governed_by relationship enables:

- Policy governance
- Rule enforcement
- Compliance management
- Mission governance
- Security governance
- Runtime governance
- AI safety controls
- Federated governance

Every governed entity SHALL have an identifiable governing authority.

---

# 3. Canonical Definition

A subject **governed_by** an object when the object's policies, rules,
or governance decisions regulate the subject's behavior.

Governance MAY define obligations, prohibitions, constraints, priorities,
or operational guidance.

---

# 4. Characteristics

The **governed_by** relationship SHALL be:

- Directed
- Normative
- Deterministic
- Explainable
- Machine readable
- Versioned

Governance SHALL remain independently auditable.

---

# 5. Relationship Signature

```text
Governed Entity

governed_by

Governance Authority
```

---

# 6. Semantic Meaning

The governed entity SHALL comply with governance decisions defined by
the governing authority.

Governance MAY influence:

- Execution
- Scheduling
- Resource allocation
- Security
- Compliance
- Mission priorities
- Risk tolerance

Governance SHALL NOT imply ownership.

---

# 7. Inverse Relationship

```text
Governance Authority

governs

Governed Entity
```

The inverse relationship SHALL preserve governance semantics.

---

# 8. Multiplicity

Supported cardinalities include:

- 1 → 1
- N → 1
- N → N

Multiple governance authorities MAY coexist when governance domains are
explicitly separated.

---

# 9. Valid Examples

## Runtime

```text
Runtime

governed_by

ExecutionPolicy
```

---

## Mission

```text
Mission

governed_by

MissionPolicy
```

---

## Agent

```text
Agent

governed_by

SafetyPolicy
```

---

## Plugin

```text
Plugin

governed_by

ExtensionPolicy
```

---

## Federation

```text
FederationNode

governed_by

FederationPolicy
```

---

# 10. Invalid Examples

The following SHOULD NOT use **governed_by**.

```text
PlannerService

governed_by

MemoryService
```

Use **uses**.

---

```text
Mission

governed_by

Goal
```

Use **contains**.

---

```text
Runtime

governed_by

Kernel

(as structural relationship)
```

Use **part_of** or **belongs_to**.

---

# 11. Governance Semantics

Governance MAY define:

- Obligations
- Permissions
- Prohibitions
- Priorities
- Constraints
- Compliance requirements
- Safety limits
- Audit rules

Governance SHALL remain externally inspectable.

---

# 12. Policy Evaluation

Governance engines MAY evaluate:

- Context
- Risk
- Identity
- Trust
- Resource availability
- Mission objectives
- Security state

Policy evaluation SHALL be deterministic for equivalent inputs.

---

# 13. Registry Integration

The governed_by relationship SHALL integrate with:

- POL Registry
- SEM Registry
- CAP Registry
- XRF Registry

Metadata MAY include:

```yaml
governed_entity:
governance_authority:
policy_version:
evaluation_context:
effective_from:
effective_until:
```

---

# 14. Federation

Federated SH-3 systems SHALL preserve:

- Governance identity
- Policy version
- Trust domain
- Provenance
- Auditability

Cross-domain governance SHALL remain explicitly identifiable.

---

# 15. Constraints

The **governed_by** relationship SHALL:

- Preserve governance authority
- Support explainability
- Support auditing
- Support policy evolution
- Remain implementation independent

The relationship SHALL NOT imply:

- Ownership
- Capability implementation
- Execution
- Structural composition

---

# 16. Relationship Comparison

| Relationship | Meaning |
|--------------|---------|
| governed_by | Operates under governance |
| authorized_by | Receives permission |
| constrained_by | Limited by rules or conditions |
| requires | Declares dependency |
| executes | Performs execution |

---

# 17. Examples

## Runtime Governance

```text
Runtime

governed_by

ExecutionPolicy

↓

ExecutionPolicy

governs

Runtime
```

---

## AI Safety

```text
Agent

governed_by

SafetyPolicy

↓

SafetyPolicy

governs

Agent
```

---

## Federated Governance

```text
FederationNode

governed_by

FederationPolicy

↓

FederationPolicy

governs

FederationNode
```

---

# 18. Reasoning Rules

Reasoning engines MAY infer applicable governance domains.

```text
Mission

governed_by

MissionPolicy

MissionPolicy

references

SafetyPolicy

↓

Mission

subject_to

SafetyPolicy
```

Derived governance relationships SHALL remain distinguishable from
explicit governance declarations.

---

# 19. Cross References

Related concepts:

- Policy
- Rule
- Runtime
- Mission
- Agent
- Federation
- Security

Related relationships:

- governs
- authorized_by
- constrained_by
- references

Referenced specifications:

- Policy Architecture
- Security Architecture
- Mission Architecture
- Federation Architecture
- RFC-0264 Meta Governance Architecture

---

# 20. Summary

The **governed_by** relationship defines the canonical semantic
association between a governed entity and its governing authority within
the SH-3 Ontology.

It establishes the semantic foundation for policy enforcement,
compliance, AI safety, mission governance, runtime control, and
federated governance while preserving deterministic,
implementation-independent semantics and full auditability.