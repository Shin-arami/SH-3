# SH-3 Ontology Metadata Schema

Version: 1.0.0
Status: Stable
Category: Ontology Schema
Schema ID: SCH-0300
Author: SH-3 Architecture Working Group

---

# 1. Overview

The SH-3 Ontology Metadata Schema defines the canonical structure for
semantic metadata attached to ontology entities and relationships.

Metadata provides additional descriptive, operational, and contextual
information without changing the fundamental identity of an object.

Metadata enables:

- Discovery
- Classification
- Filtering
- Reasoning
- Validation
- Federation exchange

---

# 2. Purpose

The Metadata Schema provides:

- Semantic annotation
- Object classification
- Search optimization
- Runtime visibility
- Governance information
- Lifecycle information

---

# 3. Metadata Model

Canonical structure:

```text
Metadata

├── Classification
├── Description
├── Ownership
├── Lifecycle
├── Operational
├── Semantic
└── Federation
```

---

# 4. Metadata Schema

Canonical format:

```yaml
metadata:

  description:

  classification:

  tags:

  domain:

  owner:

  lifecycle:

  operational:

  semantic:

  federation:
```

---

# 5. Description

Optional:

```yaml
description:
```

Defines human-readable semantic explanation.

Example:

```yaml
description:
  Event driven runtime communication service
```

---

# 6. Classification

Optional:

```yaml
classification:
```

Defines semantic grouping.

Example:

```yaml
classification:

  category:
    Runtime

  layer:
    Infrastructure
```

---

# 7. Tags

Optional:

```yaml
tags:
```

Used for discovery and indexing.

Example:

```yaml
tags:

  - event-driven

  - runtime

  - kernel
```

---

# 8. Domain

Optional:

```yaml
domain:
```

Defines operational or semantic domain.

Examples:

```yaml
domain:
  Runtime
```

```yaml
domain:
  Cognition
```

```yaml
domain:
  Federation
```

---

# 9. Ownership Metadata

Optional:

```yaml
owner:
```

Defines responsible authority.

Example:

```yaml
owner:

  organization:
    SH-3 Core Team

  authority:
    Runtime Governance
```

Ownership SHALL NOT imply execution authority.

---

# 10. Lifecycle Metadata

Optional:

```yaml
lifecycle:
```

Structure:

```yaml
lifecycle:

  created:

  updated:

  status:

  deprecated:
```

---

# 11. Operational Metadata

Optional:

```yaml
operational:
```

Defines runtime-related information.

Example:

```yaml
operational:

  availability:
    production

  criticality:
    high

  monitoring:
    enabled
```

---

# 12. Semantic Metadata

Optional:

```yaml
semantic:
```

Defines reasoning-related attributes.

Example:

```yaml
semantic:

  importance:
    0.9

  confidence:
    0.95

  abstraction_level:
    system
```

---

# 13. Capability Metadata

For capability entities:

```yaml
capability:

  interface:

  requirements:

  constraints:
```

---

# 14. Policy Metadata

For policy entities:

```yaml
policy:

  authority:

  scope:

  priority:
```

---

# 15. Federation Metadata

Federated objects SHALL define:

```yaml
federation:

  node_id:

  trust_domain:

  visibility:
```

---

# 16. Visibility Levels

Supported values:

```text
public
federated
internal
private
```

---

# 17. Metadata Validation

Validator SHALL verify:

- Field type
- Allowed values
- Required attributes
- Domain compatibility
- Security restrictions

---

# 18. Metadata Inheritance

Metadata MAY inherit from parent entities.

Example:

```text
Runtime

metadata:

domain:
Runtime


Component

part_of

Runtime
```

Component MAY inherit Runtime domain.

---

# 19. Override Rules

Inherited metadata SHALL NOT override:

- Identity
- Provenance
- Security constraints
- Trust information

---

# 20. Search Integration

Metadata supports:

- Semantic indexing
- Filtering
- Ranking
- Discovery

Example:

```text
Find:

domain = Cognition

AND

tag = planner
```

---

# 21. Federation Compatibility

Federated metadata SHALL preserve:

- Source node
- Version
- Visibility
- Trust context

---

# 22. Security Requirements

Metadata SHALL NOT:

- Expose restricted information
- Modify authorization
- Alter identity
- Hide provenance

---

# 23. Cross References

Related:

- Entity Schema
- Relationship Schema
- Provenance Schema
- Federation Schema
- Validation Rules

Referenced:

- RFC-0263 SH-3 Architecture Intelligence Architecture
- RFC-0264 Meta Governance Architecture
- RFC-0265 Federation Architecture
- RFC-0269 Semantic Intelligence Layer Architecture

---

# 24. Summary

The SH-3 Ontology Metadata Schema defines the standard semantic
annotation structure for ontology objects.

It enables discovery, classification, reasoning context, runtime
visibility, and federation interoperability while preserving identity,
security, and provenance guarantees.