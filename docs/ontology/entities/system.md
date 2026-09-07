# SH-3 Ontology Entity: System

Version: 1.0.0
Status: Stable
Category: Ontology Entity
Entity ID: ENT-0100
Author: SH-3 Architecture Working Group

---

# 1. Overview

The SH-3 System Entity represents the highest-level semantic object
within the SH-3 Ontology hierarchy.

A System defines a complete operational, cognitive, or federated
environment composed of multiple semantic entities.

Examples:

- SH-3 Runtime System
- SH-3 Cognitive System
- SH-3 Federation System
- Autonomous Intelligence System

---

# 2. Purpose

The System Entity provides:

- Top-level identity
- Architectural boundary
- Lifecycle management
- Semantic ownership
- Entity composition root

---

# 3. Entity Definition

Canonical representation:

```yaml
entity:

  id:
    sh3.system.example

  type:
    System

  name:
    Example System

  version:
    1.0.0
```

---

# 4. Entity Type

```yaml
type:
  System
```

System is the root ontology classification.

---

# 5. Identity

Required:

```yaml
id:
```

Requirements:

- Globally unique
- Stable
- Immutable

Example:

```yaml
id:
  sh3.system.core
```

---

# 6. Description

Optional:

```yaml
description:
```

Defines system purpose and semantic scope.

Example:

```yaml
description:
  Autonomous intelligence operating environment
```

---

# 7. System Classification

System MAY define:

```yaml
classification:
```

Example:

```yaml
classification:

  domain:
    Intelligence

  category:
    AutonomousSystem
```

---

# 8. Composition

A System MAY contain:

```text
System

contains

Component
```

```text
System

contains

Service
```

```text
System

contains

Agent
```

---

# 9. Supported Relationships

System supports:

| Relationship | Target |
|---|---|
| contains | Component |
| contains | Service |
| governed_by | Policy |
| provides | Capability |
| federated_with | Federation Node |

---

# 10. Required Metadata

System SHALL define:

```yaml
metadata:

  version:

  status:

  lifecycle:
```

---

# 11. Lifecycle

System lifecycle:

```text
Created

↓

Initialized

↓

Operational

↓

Maintenance

↓

Deprecated

↓

Archived
```

---

# 12. Operational State

Allowed states:

```text
initializing
active
degraded
maintenance
stopped
archived
```

---

# 13. Capability Association

System MAY provide capabilities.

Example:

```text
SH-3 System

provides

Autonomous Reasoning Capability
```

---

# 14. Governance Association

Every production System SHOULD define:

```text
System

governed_by

Policy
```

---

# 15. Federation Association

Federated systems SHALL define:

```text
System

federated_with

Federation Node
```

---

# 16. Validation Requirements

System Validator SHALL verify:

- Unique identity
- Valid type
- Version existence
- Lifecycle state
- Relationship validity
- Provenance availability

---

# 17. Provenance

System SHALL maintain:

```yaml
provenance:

  created_by:

  created_at:

  history:
```

---

# 18. Security Requirements

System Entity SHALL NOT:

- Override policies
- Remove constraints
- Modify provenance
- Bypass governance

---

# 19. Federation Compatibility

Federated Systems SHALL include:

```yaml
federation:

  node_id:

  trust_domain:

  ontology_version:
```

---

# 20. Example

```yaml
entity:

  id:
    sh3.system.core

  type:
    System

  name:
    SH-3 Core Intelligence System

  version:
    1.0.0

  metadata:

    domain:
      Artificial Intelligence

    status:
      active
```

---

# 21. Cross References

Related:

- Component Entity
- Service Entity
- Agent Entity
- Capability Entity
- Policy Entity
- Federation Node Entity

Referenced:

- RFC-0261 SH-3 Architecture Framework
- RFC-0263 SH-3 Architecture Intelligence Architecture
- RFC-0265 Federation Architecture

---

# 22. Summary

The SH-3 System Entity defines the top-level semantic boundary of an
SH-3 environment.

It provides the root structure for composition, governance,
capabilities, lifecycle control, and federation participation,
forming the foundation of the SH-3 Ontology hierarchy.