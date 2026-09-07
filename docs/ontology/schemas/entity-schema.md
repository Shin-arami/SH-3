# SH-3 Ontology Entity Schema

Version: 1.0.0
Status: Stable
Category: Ontology Schema
Schema ID: SCH-0100
Author: SH-3 Architecture Working Group

---

# 1. Overview

The SH-3 Ontology Entity Schema defines the canonical structure for
all semantic entities registered within the SH-3 ecosystem.

An Entity represents any identifiable semantic object including:

- Components
- Services
- Agents
- Capabilities
- Policies
- Knowledge Objects
- Runtime Objects
- Federation Objects

---

# 2. Purpose

The Entity Schema provides:

- Semantic identity
- Type definition
- Version management
- Lifecycle control
- Relationship compatibility
- Provenance tracking

---

# 3. Entity Model

Canonical representation:

```text
Entity

├── Identity
├── Classification
├── Metadata
├── Lifecycle
├── Relationships
└── Provenance
```

---

# 4. Required Fields

Every SH-3 Entity SHALL define:

```yaml
id:
type:
name:
version:
status:
```

---

# 5. Entity Schema

Canonical format:

```yaml
entity:
  id:
  type:
  name:
  description:
  version:
  status:
  metadata:
  relationships:
  provenance:
```

---

# 6. Identity Section

## Required

```yaml
id:
```

Definition:

Unique identifier of the entity.

Requirements:

- Globally unique
- Stable
- Immutable

Example:

```yaml
id: sh3.runtime.event_bus
```

---

# 7. Type Section

## Required

```yaml
type:
```

Defines ontology classification.

Examples:

```yaml
type: Service
```

```yaml
type: Capability
```

```yaml
type: Agent
```

---

# 8. Name Section

## Required

```yaml
name:
```

Human-readable entity name.

Example:

```yaml
name: Event Bus
```

---

# 9. Description Section

Optional:

```yaml
description:
```

Provides semantic explanation.

---

# 10. Version Section

Required:

```yaml
version:
```

Format:

```yaml
version: 1.0.0
```

Version changes SHALL preserve lineage.

---

# 11. Status Section

Required:

```yaml
status:
```

Allowed values:

```text
draft
experimental
stable
deprecated
archived
```

---

# 12. Metadata Section

Optional:

```yaml
metadata:
```

May include:

```yaml
owner:
domain:
tags:
category:
```

---

# 13. Relationship Section

Optional:

```yaml
relationships:
```

Example:

```yaml
relationships:

  - type:
      provides
    target:
      sh3.capability.event_processing

  - type:
      requires
    target:
      sh3.infrastructure.storage
```

---

# 14. Provenance Section

Required for knowledge objects:

```yaml
provenance:
```

Example:

```yaml
provenance:

  source:
    internal

  created_by:
    ontology_builder

  created_at:
    timestamp
```

---

# 15. Lifecycle Section

Entities MAY define lifecycle:

```yaml
lifecycle:

  created:
  updated:
  expires:
```

---

# 16. Classification

Supported entity categories:

| Category | Examples |
|---|---|
| Component | Runtime |
| Service | Memory |
| Agent | Planner |
| Capability | Reasoning |
| Policy | Safety |
| Knowledge | Concept |
| Resource | Storage |
| Federation | Node |

---

# 17. Entity Constraints

Entities SHALL:

- Have unique identity
- Have valid type
- Preserve version
- Maintain provenance
- Follow ontology rules

---

# 18. Invalid Entity Example

Invalid:

```yaml
entity:

  name:
    Memory

  description:
    Storage system
```

Missing:

```yaml
id:
type:
version:
```

---

# 19. Validation Integration

Entity validation SHALL verify:

- Required fields
- Type existence
- Version format
- Relationship validity
- Provenance availability

---

# 20. Registry Integration

Entity Schema integrates with:

- Semantic Registry
- Knowledge Registry
- Capability Registry
- Federation Registry

---

# 21. Federation Compatibility

Federated entities SHALL additionally define:

```yaml
federation:

  node_id:
  trust_domain:
```

---

# 22. Security Requirements

Entity definitions SHALL NOT:

- Override authorization
- Remove constraints
- Modify provenance
- Bypass validation

---

# 23. Cross References

Related:

- Relationship Schema
- Metadata Schema
- Provenance Schema
- Federation Schema
- Validation Rules

Referenced:

- RFC-0263 SH-3 Architecture Intelligence Architecture
- RFC-0265 Federation Architecture
- RFC-0269 Semantic Intelligence Layer Architecture

---

# 24. Summary

The SH-3 Ontology Entity Schema defines the standard semantic structure
for all entities within the SH-3 ecosystem.

It provides identity, classification, lifecycle, relationship,
provenance, and federation compatibility required for a production-grade
semantic intelligence framework.