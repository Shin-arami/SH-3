# ADR-0018: Registry as Source of Truth

Version: 2.0
Status: Accepted
Category: Architecture Decision Record
Author: SH-3 Architecture Working Group

---

# 1. Context

SH-3 consists of numerous architectural assets including components,
capabilities, services, specifications, ontologies, schemas,
deployments, and federated nodes.

Without a centralized authority, inconsistent metadata, duplicated
configuration, incompatible versions, and non-deterministic behavior
can emerge.

To preserve architectural integrity, every managed asset SHALL be
registered in an authoritative registry.

---

# 2. Decision

SH-3 adopts the architectural principle:

> **Registry is the Single Source of Truth**

Every managed architectural asset SHALL be discoverable through one or
more authoritative registries.

Runtime behavior SHALL rely on registry information rather than hidden
implementation details.

No component SHALL maintain conflicting authoritative metadata outside
an approved registry.

---

# 3. Motivation

Registry-driven architecture provides:

- Deterministic discovery
- Consistent metadata
- Version traceability
- Dependency validation
- Simplified governance
- Federation interoperability

Without centralized registries:

- Duplicate definitions appear.
- Configuration diverges.
- Discovery becomes unreliable.
- Runtime decisions become inconsistent.

---

# 4. Registry Model

SH-3 registries collectively form the architectural knowledge base.

```text
Registry System

├── Component Registry
├── Capability Registry
├── Service Registry
├── Event Registry
├── Ontology Registry
├── Schema Registry
├── Configuration Registry
├── Deployment Registry
├── Specification Registry
└── Federation Registry
```

Each registry SHALL have a clearly defined ownership and lifecycle.

---

# 5. Registry Responsibilities

Every registry SHALL provide:

```text
Registration

Lookup

Validation

Discovery

Version Tracking

Dependency Tracking

Lifecycle Management

Audit History
```

Registries SHALL expose typed interfaces.

---

# 6. Managed Assets

Registries SHALL manage:

```text
Components

Capabilities

Services

Agents

Events

Policies

Schemas

Ontologies

Knowledge Assets

Packages

Deployments

Federation Nodes
```

Every managed asset SHALL possess a globally unique identifier.

---

# 7. Metadata Requirements

Every registry entry SHALL include:

```text
Identifier

Type

Version

Owner

Lifecycle State

Dependencies

Compatibility

Security Classification

Registration Timestamp

Last Updated
```

Optional metadata MAY be added while preserving compatibility.

---

# 8. Registration Rules

Assets SHALL be registered before operational use.

Registration SHALL validate:

```text
Identity

Schema

Version

Dependencies

Conformance

Security

Semantic Integrity
```

Failed validation SHALL prevent registration.

---

# 9. Discovery

All runtime discovery SHALL occur through registries.

Discovery SHALL support:

```text
Identifier

Type

Capability

Keyword

Semantic Query

Version

Compatibility

Status
```

Discovery SHALL be deterministic.

---

# 10. Dependency Management

Registries SHALL maintain dependency graphs.

Dependencies SHALL support:

```text
Validation

Impact Analysis

Cycle Detection

Migration Planning

Upgrade Planning
```

Circular dependencies SHALL be rejected.

---

# 11. Version Management

Registries SHALL record:

```text
Current Version

Supported Versions

Deprecated Versions

Compatibility Class

Migration Path
```

Historical records SHALL remain available.

---

# 12. Runtime Integration

Runtime SHALL obtain metadata exclusively from registries.

Runtime SHALL NOT rely upon:

```text
Hard-coded Configuration

Implicit Discovery

Manual Dependency Resolution

Hidden Metadata
```

Runtime state SHALL remain synchronized with registry state.

---

# 13. Kernel Integration

Kernel SHALL coordinate:

```text
Registration

Activation

Dependency Resolution

Lifecycle

Validation

Authority Enforcement
```

Kernel SHALL treat registries as authoritative.

---

# 14. Federation Integration

Federated nodes SHALL synchronize selected registry information.

Synchronization MAY include:

```text
Capabilities

Protocols

Ontology Versions

Trust Metadata

Supported Profiles
```

Synchronization SHALL preserve local authority.

---

# 15. Security

Registry operations SHALL require:

```text
Authentication

Authorization

Audit Logging

Integrity Validation

Version Validation
```

Unauthorized modifications SHALL be rejected.

---

# 16. Conformance

Registry implementations SHALL comply with:

- RFC-0262 SH-3 Conformance Specification
- SSR-0001 SH-3 Specification Registry
- Schema Validation
- Lifecycle Validation
- Security Validation

Only conformant registries SHALL participate in production systems.

---

# 17. Benefits

Registry-driven architecture provides:

- Single Source of Truth
- Reliable discovery
- Strong governance
- Consistent metadata
- Deterministic runtime behavior
- Simplified federation

---

# 18. Consequences

Advantages

- Elimination of duplicate metadata
- Better dependency management
- Simplified validation
- Reliable discovery
- Improved interoperability

Trade-offs

- Additional registry infrastructure
- Increased metadata management
- Stronger governance requirements
- Registry availability becomes critical

These trade-offs are accepted to ensure architectural consistency and
deterministic operation.

---

# 19. References

Architecture documents:

- architecture/registry.md
- architecture/reference-architecture.md
- architecture/dependency-map.md
- architecture/conformance.md

Related RFCs:

- RFC-0014 Registry
- RFC-0117 Kernel Service Registry Architecture
- RFC-0145 Service Discovery Architecture
- RFC-0261 SH-3 Architecture Framework
- RFC-0262 SH-3 Conformance Specification

Related Specifications:

- SSR-0001 SH-3 Specification Registry
- MOD-0814 Architecture Schema
- SCC-0301 Conformance
- SCC-0302 Architecture
- SAT-0401 Conformance Suite