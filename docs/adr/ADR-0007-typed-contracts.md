# ADR-0007: Typed Contracts

Version: 2.0
Status: Accepted
Category: Architecture Decision Record
Author: SH-3 Architecture Working Group

---

# 1. Context

SH-3 is designed as a deterministic AI Operating System where components
communicate through well-defined contracts.

Implicit interfaces, dynamically shaped data, and undocumented payloads
introduce ambiguity, reduce interoperability, and make long-term
evolution difficult.

To ensure architectural consistency, every public interaction SHALL be
defined through explicit typed contracts.

This ADR establishes strong typing as a mandatory architectural
requirement.

---

# 2. Decision

SH-3 adopts the architectural principle:

> **Everything Typed**

Every public interface, event, configuration object, data model, and
service contract SHALL be explicitly typed.

Type definitions SHALL be treated as architectural assets rather than
implementation details.

---

# 3. Motivation

Strong typing provides:

- Deterministic behavior
- Static validation
- Interface stability
- Runtime safety
- Tooling support
- Architectural consistency

Without explicit typing:

- Interface ambiguity increases
- Runtime failures become more common
- Component replacement becomes unsafe
- Evolution becomes difficult

---

# 4. Architectural Scope

Typed contracts SHALL apply to every architectural layer.

```text
Foundation

Infrastructure

Runtime

Knowledge

Cognition

Kernel

MetaController

Autonomy

Deployment
```

No layer is exempt.

---

# 5. Typed Assets

The following SHALL be typed.

```text
Interfaces

Events

Commands

Queries

Configurations

Capabilities

Policies

Results

Exceptions

Metadata

Schemas
```

---

# 6. Contract Model

Every interaction SHALL follow:

```text
Producer

↓

Typed Contract

↓

Validation

↓

Consumer
```

Consumers SHALL depend on contract definitions rather than
implementation details.

---

# 7. Interface Requirements

Public interfaces SHALL define:

```text
Identifier

Version

Input Types

Output Types

Exceptions

Capabilities

Compatibility
```

Interfaces SHALL remain stable across compatible versions.

---

# 8. Event Contracts

Every event SHALL define:

```text
Event Identifier

Schema

Version

Source

Payload

Metadata
```

Events SHALL be immutable after publication.

---

# 9. Configuration Contracts

Configuration SHALL be:

- Typed
- Versioned
- Validated
- Traceable

Implicit configuration is prohibited.

---

# 10. Schema Validation

All contracts SHALL support validation.

Validation SHALL verify:

```text
Structure

Required Fields

Optional Fields

Types

Version

Compatibility
```

Invalid contracts SHALL be rejected.

---

# 11. Version Compatibility

Contract evolution SHALL preserve:

- Backward compatibility
- Semantic consistency
- Migration support

Breaking changes SHALL require a new major version.

---

# 12. Runtime Validation

Before execution, runtime SHALL validate:

```text
Input

Output

Configuration

Capabilities

Dependencies
```

Validation SHALL occur before processing begins.

---

# 13. Registry Integration

All contracts SHALL be registered.

Registry metadata SHALL include:

```text
Identifier

Version

Owner

Status

Dependencies

References
```

The registry SHALL act as the authoritative source.

---

# 14. Capability Integration

Capabilities SHALL reference typed contracts.

Each capability SHALL declare:

- Supported interfaces
- Required contracts
- Produced events
- Consumed events

Capability discovery SHALL use contract metadata.

---

# 15. Conformance

Typed contracts SHALL satisfy:

- RFC-0262 SH-3 Conformance Specification
- Schema Validation
- Version Validation
- Compatibility Validation

Non-conforming contracts SHALL NOT be accepted.

---

# 16. Benefits

This decision provides:

- Deterministic execution
- Compile-time validation
- Runtime safety
- Easier testing
- Better tooling
- Long-term maintainability

---

# 17. Consequences

Advantages

- Explicit interfaces
- Better interoperability
- Easier evolution
- Safer component replacement
- Improved documentation

Trade-offs

- Additional schema maintenance
- Version management overhead
- More formal interface design

These trade-offs are accepted to ensure architectural integrity.

---

# 18. References

Architecture documents:

- architecture/conformance.md
- architecture/reference-architecture.md
- architecture/registry.md
- architecture/security-model.md

Related RFCs:

- RFC-0151 Data Contract Architecture
- RFC-0152 Event Bus Architecture
- RFC-0174 Configuration Architecture
- RFC-0261 SH-3 Architecture Framework
- RFC-0262 SH-3 Conformance Specification
- MOD-0801 Event Schema
- MOD-0814 Architecture Schema
