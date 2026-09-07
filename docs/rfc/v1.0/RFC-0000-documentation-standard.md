# RFC-0000

**Title:** SH-3 Documentation Standard

**Document ID:** RFC-0000

**Version:** 1.0

**Status:** Accepted

**Author:** SH-3 Project

**Category:** Process

**Target Version:** SH-3 Complete Edition

---

# Abstract

This document defines the official documentation standard used throughout the SH-3 project.

Every specification, architectural document, API reference, proposal, and implementation guideline SHALL follow the conventions defined in this document.

The primary objectives are consistency, maintainability, long-term evolution, and implementation independence.

This RFC is normative.

---

# Motivation

SH-3 is designed as a long-lived software platform rather than a collection of source files.

As the project grows, documentation becomes a critical architectural asset.

Without a unified documentation standard, multiple problems emerge:

- inconsistent terminology
- incompatible specifications
- undocumented behavior
- unclear responsibilities
- duplicated design decisions
- implementation divergence

This RFC establishes one authoritative documentation format for the entire project.

---

# Goals

The documentation system SHALL:

- define one official specification format
- separate architecture from implementation
- support long-term maintenance
- simplify onboarding
- improve review quality
- reduce ambiguity
- allow future automation

---

# Non-Goals

This document does not define:

- implementation details
- coding style
- programming language rules
- runtime behavior
- public APIs

Those topics belong to their respective RFCs.

---

# Documentation Hierarchy

The documentation hierarchy is defined as follows.

```
Architecture
        │
        ▼
RFC
        │
        ▼
ADR
        │
        ▼
API Specification
        │
        ▼
Implementation
        │
        ▼
Tests
```

Each layer depends only on the layer above.

Implementation must never become the source of architectural truth.

---

# Source of Truth

Each artifact owns one responsibility.

| Document | Responsibility |
|-----------|----------------|
| architecture.md | Overall architecture |
| RFC | Technical specification |
| ADR | Design decisions |
| API Specification | Public contracts |
| Source Code | Implementation |
| Tests | Behavioral verification |

No document should duplicate another document.

---

# Repository Documentation Layout

```
docs/
│
├── architecture.md
│
├── rfcs/
│
├── adr/
│
├── api/
│
├── sip/
│
├── development/
│
├── diagrams/
│
├── references/
│
└── roadmap.md
```

Each directory owns a distinct responsibility.

---

# RFC Numbering

RFCs use sequential numbering.

Examples:

```
RFC-0000 Documentation Standard

RFC-0001 Event System

RFC-0002 Runtime

RFC-0003 Kernel

RFC-0004 Planner
```

RFC numbers are never reused.

Deprecated RFCs remain archived.

---

# ADR Numbering

Architecture Decision Records use sequential numbering.

Examples:

```
ADR-0001 Layered Architecture

ADR-0002 Event Driven Architecture

ADR-0003 Runtime Context

ADR-0004 Dependency Rules
```

ADR numbers remain permanent.

---

# SIP Numbering

Improvement proposals use sequential numbering.

Examples:

```
SIP-0001 Distributed Runtime

SIP-0002 Multi-Agent Coordination

SIP-0003 Neural Memory

SIP-0004 World Model
```

SIPs describe future evolution.

They are not implementation commitments.

---

# API Specification Numbering

API specifications are organized by subsystem.

Examples:

```
api/

event_api.md

runtime_api.md

storage_api.md

planner_api.md
```

API documents describe public contracts only.

---

# RFC Structure

Every RFC SHALL contain the following sections.

```
Title

Status

Abstract

Motivation

Goals

Non-Goals

Requirements

Architecture

Public Interfaces

Internal Design

Lifecycle

Failure Handling

Thread Safety

Security

Performance

Observability

Compatibility

Migration

Future Work

References
```

Additional sections may be introduced when justified.

---

# RFC Status

Every RFC shall declare one status.

Possible values include:

- Draft
- Proposed
- Accepted
- Implemented
- Deprecated
- Replaced

Status changes require project review.

---

# Normative Language

The following words have normative meaning.

| Word | Meaning |
|------|---------|
| SHALL | Mandatory |
| SHALL NOT | Forbidden |
| SHOULD | Strong recommendation |
| SHOULD NOT | Discouraged |
| MAY | Optional |
| OPTIONAL | Entirely implementation dependent |

These definitions follow established engineering standards.

---

# Terminology

Documents should use consistent terminology.

Preferred terms include:

- Component
- Module
- Service
- Layer
- Runtime
- Event
- Context
- Registry
- Pipeline
- Plugin
- Snapshot

Avoid introducing synonyms unless necessary.

---

# Diagrams

Architectural diagrams should use Mermaid whenever practical.

Preferred diagram types:

- flowchart
- graph
- sequenceDiagram
- stateDiagram
- classDiagram

Diagrams should complement specifications rather than replace them.

---

# Code Examples

Code examples are informative.

They do not define architecture.

Normative behavior shall always be described in text.

---

# Tables

Tables should be preferred when describing:

- responsibilities
- dependencies
- compatibility
- interfaces
- configuration
- lifecycle

Large narrative descriptions should be avoided where tables improve clarity.

---

# Cross References

Documents should reference related specifications.

Example:

```
See:

RFC-0002 Runtime

ADR-0003 Runtime Context

API runtime_api.md
```

Cross references reduce duplication.

---

# Versioning

Every document shall include:

- Version
- Status
- Last Updated
- Target SH-3 Version

Major architectural changes require version updates.

---

# Review Process

Every RFC follows this lifecycle.

```
Draft

↓

Review

↓

Revision

↓

Accepted

↓

Implementation

↓

Maintenance
```

Implementation shall not begin before acceptance unless explicitly approved.

---

# Change Management

Breaking documentation changes require:

- revision history
- migration guidance
- compatibility notes

Minor editorial corrections do not require architectural review.

---

# File Naming

Documentation files use lowercase.

Words are separated using hyphens.

Examples:

```
event-system.md

runtime-api.md

dependency-rules.md
```

Avoid spaces.

Avoid camelCase.

---

# Markdown Rules

Documentation shall follow GitHub Flavored Markdown.

Required features:

- fenced code blocks
- tables
- headings
- Mermaid diagrams
- ordered lists
- unordered lists

HTML should be avoided unless required.

---

# Responsibility Boundaries

Architecture documents define system structure.

RFCs define technical behavior.

ADRs explain architectural decisions.

APIs define contracts.

Implementations realize specifications.

Tests verify implementations.

These responsibilities must never overlap.

---

# Compliance

A document is considered SH-3 compliant when it:

- follows this structure
- uses normative language correctly
- defines responsibilities explicitly
- avoids ambiguity
- maintains terminology consistency

Compliance reviews are mandatory before acceptance.

---

# Future Evolution

This documentation standard is expected to evolve.

Future revisions may introduce:

- automated specification validation
- generated API documentation
- architecture linting
- traceability tooling
- documentation quality metrics

Backward compatibility should be preserved whenever practical.

---

# References

- SH-3 Architecture Specification v2.1
- RFC-2119
- RFC-8174
- Rust RFC Process
- Kubernetes Enhancement Proposal (KEP)
- Python Enhancement Proposal (PEP)

---

# End of RFC-0000
