# SH-3 Ontology Relationship Schema

Version: 1.0.0
Status: Stable
Category: Ontology Schema
Schema ID: SCH-0200
Author: SH-3 Architecture Working Group

---

# 1. Overview

The SH-3 Ontology Relationship Schema defines the canonical structure
for semantic relationships connecting ontology entities.

A Relationship represents a typed semantic connection between:

- Entities
- Capabilities
- Services
- Policies
- Knowledge Objects
- Federation Nodes

---

# 2. Purpose

The Relationship Schema provides:

- Semantic graph connectivity
- Type-safe relationships
- Direction control
- Cardinality validation
- Reasoning compatibility
- Provenance tracking

---

# 3. Relationship Model

Canonical representation:

```text
Subject

     |

 Relationship

     |

Object
```

---

# 4. Required Fields

Every Relationship SHALL define:

```yaml
id:
type:
subject:
object:
version:
```

---

# 5. Relationship Schema

Canonical format:

```yaml
relationship:

  id:

  type:

  subject:

  object:

  inverse:

  metadata:

  constraints:

  provenance:
```

---

# 6. Relationship Identity

## Required

```yaml
id:
```

Definition:

Unique identifier of the relationship instance.

Example:

```yaml
id:
rel.runtime.provides.event_processing
```

---

# 7. Relationship Type

## Required

```yaml
type:
```

Defines semantic relationship class.

Examples:

```yaml
type:
provides
```

```yaml
type:
requires
```

```yaml
type:
implements
```

---

# 8. Subject Definition

## Required

```yaml
subject:
```

The entity initiating the relationship.

Example:

```yaml
subject:

  id:
    sh3.runtime.event_bus

  type:
    Service
```

---

# 9. Object Definition

## Required

```yaml
object:
```

The target entity.

Example:

```yaml
object:

  id:
    sh3.capability.event_processing

  type:
    Capability
```

---

# 10. Direction Rules

Relationships SHALL preserve direction.

Example:

Valid:

```text
Service

provides

Capability
```

Invalid:

```text
Capability

provides

Service
```

unless separately defined.

---

# 11. Inverse Relationship

Optional:

```yaml
inverse:
```

Example:

```yaml
type:
provides

inverse:
provided_by
```

---

# 12. Relationship Categories

Supported categories:

| Category | Examples |
|---|---|
| Structural | part_of |
| Capability | implements |
| Dependency | requires |
| Behavioral | executes |
| Knowledge | derived_from |
| Governance | governed_by |
| Federation | trusted_by |

---

# 13. Cardinality

Relationships MAY define:

```yaml
cardinality:
```

Examples:

```yaml
1:N
```

```yaml
N:N
```

---

# 14. Metadata Section

Optional:

```yaml
metadata:
```

May include:

```yaml
confidence:
priority:
scope:
```

---

# 15. Constraint Section

Optional:

```yaml
constraints:
```

Defines relationship restrictions.

Example:

```yaml
constraints:

  allowed_subject:
    Service

  allowed_object:
    Capability
```

---

# 16. Provenance Section

Required for inferred relationships:

```yaml
provenance:
```

Example:

```yaml
provenance:

  source:
    inference_engine

  rule:
    RULE-INF-010
```

---

# 17. Relationship Validation

Validator SHALL check:

- Relationship existence
- Subject validity
- Object validity
- Direction correctness
- Cardinality
- Constraint compliance

---

# 18. Invalid Relationship Example

Invalid:

```yaml
relationship:

 type:
   provides

 subject:
   Capability

 object:
   Service
```

Reason:

Relationship direction violation.

---

# 19. Inference Compatibility

Relationships MAY participate in inference.

Example:

```text
A implements B

↓

A provides B
```

Derived relationships SHALL preserve provenance.

---

# 20. Federation Compatibility

Federated relationships SHALL include:

```yaml
federation:

 source_node:
 target_node:
 trust_context:
```

---

# 21. Security Requirements

Relationships SHALL NOT:

- Grant unauthorized permissions
- Override constraints
- Remove governance rules
- Modify identity

---

# 22. Registry Integration

Relationship Schema integrates with:

- Semantic Registry
- Knowledge Graph
- Reasoning Engine
- Federation Registry

---

# 23. Cross References

Related:

- Entity Schema
- Metadata Schema
- Provenance Schema
- Federation Schema
- Ontology Relationship Definitions

Referenced:

- RFC-0263 SH-3 Architecture Intelligence Architecture
- RFC-0264 Meta Governance Architecture
- RFC-0265 Federation Architecture
- RFC-0269 Semantic Intelligence Layer Architecture

---

# 24. Summary

The SH-3 Ontology Relationship Schema defines the formal structure of
semantic connections between entities.

It enables typed Knowledge Graph construction, deterministic reasoning,
relationship validation, federation interoperability, and production
grade semantic intelligence across the SH-3 ecosystem.