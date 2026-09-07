# SH-3 Relationship: trusted_by

Version: 1.0.0
Status: Stable
Category: Ontology Relationship
Relationship ID: REL-0603
Canonical Name: trusted_by
Predicate: trusted_by
Inverse Predicate: trusts
Author: SH-3 Architecture Working Group

---

# 1. Overview

The **trusted_by** relationship represents the canonical semantic
association in which one entity is recognized as trustworthy by another
entity.

Trust establishes confidence in identity, behavior, reliability, or
authority without implying permission, governance, or ownership.

Unlike **authorized_by**, which grants permission,
**trusted_by** establishes confidence.

---

# 2. Purpose

The trusted_by relationship enables:

- Federated identity
- Trust management
- Secure communication
- Agent collaboration
- Cross-domain federation
- Reputation management
- Security decisions
- Autonomous coordination

Trust SHALL remain explicit and auditable.

---

# 3. Canonical Definition

A subject **trusted_by** an object when the object recognizes the
subject as a trusted entity based on identity, evidence, policy, history,
or verification.

Trust MAY be absolute, conditional, or context dependent.

---

# 4. Characteristics

The **trusted_by** relationship SHALL be:

- Directed
- Security-oriented
- Evidence-based
- Auditable
- Machine readable
- Versioned

Trust SHALL preserve evaluation context.

---

# 5. Relationship Signature

```text
Trusted Entity

trusted_by

Trust Authority
```

---

# 6. Semantic Meaning

The trust authority assigns confidence to the trusted entity.

Trust MAY consider:

- Identity
- Authentication
- Reputation
- Historical behavior
- Security posture
- Compliance status
- Verification evidence

Trust SHALL NOT imply authorization.

---

# 7. Inverse Relationship

```text
Trust Authority

trusts

Trusted Entity
```

The inverse relationship SHALL preserve trust semantics.

---

# 8. Multiplicity

Supported cardinalities include:

- 1 → 1
- 1 → N
- N → N

Entities MAY participate in multiple trust relationships.

---

# 9. Valid Examples

## Federation Node

```text
RemoteNode

trusted_by

FederationAuthority
```

---

## Agent Network

```text
AgentA

trusted_by

CoordinatorAgent
```

---

## Service Federation

```text
ExternalService

trusted_by

ServiceRegistry
```

---

## Knowledge Source

```text
KnowledgeProvider

trusted_by

KnowledgeSystem
```

---

## Plugin Security

```text
Plugin

trusted_by

PluginRegistry
```

---

# 10. Invalid Examples

The following SHOULD NOT use **trusted_by**.

```text
Agent

trusted_by

PermissionPolicy
```

Use **authorized_by**.

---

```text
Runtime

trusted_by

ExecutionPolicy
```

Use **governed_by**.

---

```text
Service

trusted_by

Database

(as dependency)
```

Use **requires** or **uses**.

---

# 11. Trust Semantics

Trust MAY include:

- Confidence score
- Trust level
- Verification method
- Identity proof
- Security assessment
- Reputation history
- Expiration

Trust SHALL remain explainable.

---

# 12. Trust Models

Supported models MAY include:

- Identity trust
- Reputation trust
- Capability trust
- Evidence-based trust
- Policy-based trust
- Federated trust

Trust model SHALL be explicit.

---

# 13. Registry Integration

The trusted_by relationship SHALL integrate with:

- FED Registry
- SEC Registry
- ID Registry
- CAP Registry
- XRF Registry

Metadata MAY include:

```yaml
trusted_entity:
trust_authority:
trust_level:
verification:
confidence:
effective_period:
```

---

# 14. Federation

Federated SH-3 systems SHALL preserve:

- Identity
- Trust authority
- Trust scope
- Verification evidence
- Expiration
- Audit history

Trust decisions SHALL remain traceable across federation boundaries.

---

# 15. Constraints

The **trusted_by** relationship SHALL:

- Preserve trust provenance
- Support secure federation
- Support identity management
- Support risk evaluation
- Remain implementation independent

The relationship SHALL NOT imply:

- Authorization
- Governance
- Ownership
- Synchronization
- Replication

---

# 16. Relationship Comparison

| Relationship | Meaning |
|--------------|---------|
| synchronized_with | Maintains consistency |
| replicated_to | Creates distributed copy |
| trusted_by | Establishes confidence |
| authorized_by | Grants permission |
| governed_by | Defines control |

---

# 17. Examples

## Federated Intelligence

```text
AgentNode

trusted_by

FederationController

↓

AgentNode

authorized_by

CapabilityPolicy
```

---

## Secure Plugin System

```text
Plugin

trusted_by

PluginRegistry

↓

Plugin

authorized_by

ExtensionPolicy
```

---

## Multi-Agent Coordination

```text
WorkerAgent

trusted_by

CoordinatorAgent

↓

WorkerAgent

synchronized_with

CoordinatorAgent
```

---

# 18. Reasoning Rules

Reasoning engines MAY evaluate trust inheritance.

```text
Agent

trusted_by

Organization

Organization

trusted_by

FederationAuthority

↓

Agent

recognized_within

FederationDomain
```

Trust inheritance SHALL require explicit federation policy.

---

# 19. Cross References

Related concepts:

- Trust
- Identity
- Federation
- Security
- Agent
- Authority
- Reputation

Related relationships:

- synchronized_with
- replicated_to
- authorized_by
- governed_by
- constrained_by

Referenced specifications:

- Federation Architecture
- Security Architecture
- Identity Architecture
- Trust Architecture
- RFC-0265 Federation Architecture
- RFC-0266 Collective Intelligence Architecture

---

# 20. Summary

The **trusted_by** relationship defines the canonical semantic
association between entities participating in trust relationships within
the SH-3 Ontology.

It establishes the foundation for federated identity, secure
communication, multi-agent collaboration, autonomous coordination, and
trust-aware intelligence while preserving explicit provenance,
auditability, and implementation-independent semantics.