# SH-3 Relationship: authorized_by

Version: 1.0.0
Status: Stable
Category: Ontology Relationship
Relationship ID: REL-0502
Canonical Name: authorized_by
Predicate: authorized_by
Inverse Predicate: authorizes
Author: SH-3 Architecture Working Group

---

# 1. Overview

The **authorized_by** relationship represents the canonical semantic
association in which an entity receives permission, approval, or
execution authority from another entity.

Unlike **governed_by**, which defines the governing framework,
**authorized_by** defines explicit permission.

Authorization determines what an entity is allowed to perform.

---

# 2. Purpose

The authorized_by relationship enables:

- Permission management
- Access control
- Action authorization
- Tool execution control
- Agent capability control
- Security enforcement
- Compliance verification
- Federated trust management

Every privileged action SHALL have an identifiable authorization source.

---

# 3. Canonical Definition

A subject **authorized_by** an object when the object grants permission
or authority for the subject to perform a specific action, access a
resource, or execute a capability.

Authorization SHALL be explicit or policy-derived.

---

# 4. Characteristics

The **authorized_by** relationship SHALL be:

- Directed
- Security-oriented
- Deterministic
- Auditable
- Machine readable
- Versioned

Authorization decisions SHALL be explainable.

---

# 5. Relationship Signature

```text
Authorized Entity

authorized_by

Authorization Authority
```

---

# 6. Semantic Meaning

The authorization authority grants permission to the authorized entity.

Authorization MAY define:

- Allowed actions
- Scope
- Resources
- Time period
- Conditions
- Identity requirements
- Trust level

Authorization SHALL NOT imply ownership.

---

# 7. Inverse Relationship

```text
Authorization Authority

authorizes

Authorized Entity
```

The inverse relationship SHALL preserve authorization semantics.

---

# 8. Multiplicity

Supported cardinalities include:

- 1 → 1
- 1 → N
- N → N

Multiple authorization sources MAY apply simultaneously.

---

# 9. Valid Examples

## Agent Action

```text
Agent

authorized_by

AgentPermissionPolicy
```

---

## Tool Execution

```text
ToolExecutor

authorized_by

ToolAccessPolicy
```

---

## Runtime Resource

```text
Runtime

authorized_by

ResourcePermission
```

---

## Plugin

```text
Plugin

authorized_by

ExtensionPermission
```

---

## Federation

```text
RemoteNode

authorized_by

FederationTrustPolicy
```

---

# 10. Invalid Examples

The following SHOULD NOT use **authorized_by**.

```text
Agent

authorized_by

Mission
```

Use **governed_by** or **assigned_to**.

---

```text
Runtime

authorized_by

Scheduler
```

Use execution relationships.

---

```text
Service

authorized_by

Capability
```

Use **implements** or **provides**.

---

# 11. Authorization Semantics

Authorization MAY include:

- Subject identity
- Action type
- Resource scope
- Conditions
- Expiration
- Trust level
- Policy reference

Authorization evaluation SHALL remain deterministic.

---

# 12. Policy Evaluation

Authorization engines MAY evaluate:

- Identity
- Role
- Capability
- Context
- Risk
- Trust
- Security state
- Mission constraints

Authorization result SHALL be explainable.

---

# 13. Registry Integration

The authorized_by relationship SHALL integrate with:

- POL Registry
- SEC Registry
- CAP Registry
- XRF Registry

Metadata MAY include:

```yaml
authorized_entity:
authority:
permission:
scope:
conditions:
expiration:
decision:
```

---

# 14. Federation

Federated SH-3 systems SHALL preserve:

- Authorization authority
- Trust relationship
- Permission scope
- Policy version
- Audit records

Cross-domain authorization SHALL remain explicitly identifiable.

---

# 15. Constraints

The **authorized_by** relationship SHALL:

- Preserve authorization provenance
- Support access control
- Support auditing
- Support security decisions
- Remain implementation independent

The relationship SHALL NOT imply:

- Governance
- Ownership
- Execution
- Structural composition

---

# 16. Relationship Comparison

| Relationship | Meaning |
|--------------|---------|
| governed_by | Operates under policy |
| authorized_by | Receives permission |
| constrained_by | Is limited by conditions |
| requires | Declares dependency |
| executes | Performs execution |

---

# 17. Examples

## Agent Tool Access

```text
Agent

authorized_by

ToolPermissionPolicy

↓

Agent

invokes

Tool
```

---

## Runtime Permission

```text
Runtime

authorized_by

ExecutionPermission

↓

Runtime

executes

Task
```

---

## Federated Access

```text
RemoteService

authorized_by

FederationTrustPolicy

↓

RemoteService

provides

Capability
```

---

# 18. Reasoning Rules

Reasoning engines MAY infer authorization scope.

```text
Agent

authorized_by

AgentPolicy

AgentPolicy

governed_by

SafetyFramework

↓

Agent

operates_under

SafetyFramework
```

Authorization SHALL NOT be inferred as ownership.

---

# 19. Cross References

Related concepts:

- Permission
- Policy
- Security
- Agent
- Tool
- Capability
- Federation

Related relationships:

- governed_by
- constrained_by
- provides
- invokes
- executes

Referenced specifications:

- Security Architecture
- Policy Engine Architecture
- Agent Architecture
- Federation Architecture
- RFC-0264 Meta Governance Architecture

---

# 20. Summary

The **authorized_by** relationship defines the canonical semantic
association between an entity and the authority granting permission
within the SH-3 Ontology.

It establishes the foundation for access control, security enforcement,
agent permissions, tool authorization, runtime protection, and
federated trust management while preserving deterministic,
auditable, and implementation-independent governance semantics.