# SH-3 Ontology Validation Rules

Version: 1.0.0
Status: Stable
Category: Ontology Rules
Rule Set ID: RULE-0300
Author: SH-3 Architecture Working Group

---

# 1. Overview

The SH-3 Ontology Validation Rules define the requirements for
validating ontology entities, relationships, metadata, schemas, and
knowledge structures.

Validation ensures that all ontology objects conform to SH-3 semantic,
structural, and operational specifications.

Validation SHALL verify:

- Completeness
- Correctness
- Schema compliance
- Type compliance
- Relationship validity
- Metadata integrity

---

# 2. Purpose

Validation Rules enable:

- Ontology quality assurance
- Knowledge Graph reliability
- Schema verification
- Runtime safety
- Automated registration
- Semantic governance

---

# 3. Validation Principles

SH-3 validation follows:

```text
Input Knowledge

        |

Validation Engine

        |

Validated Knowledge
```

Invalid knowledge SHALL NOT enter the trusted Knowledge Graph.

---

# 4. Validation Categories

| Category | Purpose |
|---|---|
| Entity Validation | Entity correctness |
| Relationship Validation | Relationship correctness |
| Metadata Validation | Metadata completeness |
| Schema Validation | Structure compliance |
| Semantic Validation | Meaning verification |

---

# 5. Entity Validation Rules

## RULE-VAL-001

## Required Entity Identity

Every entity SHALL define:

```yaml
id:
type:
version:
```

Invalid:

```yaml
name:
description:
```

without identity.

---

# 6. Entity Type Validation

## RULE-VAL-002

Entity type SHALL exist in the SH-3 Ontology Registry.

Valid:

```text
Agent
Service
Capability
Policy
Knowledge
```

Invalid:

```text
UnknownEntityType
```

---

# 7. Entity Version Validation

## RULE-VAL-003

Every entity SHALL contain:

```yaml
version:
created:
updated:
```

Version changes SHALL preserve lineage.

---

# 8. Relationship Validation Rules

## RULE-VAL-010

## Relationship Type Validation

Every relationship SHALL exist in:

```text
docs/ontology/relationships/
```

Invalid:

```text
unknown_relation
```

---

# 9. Relationship Endpoint Validation

A relationship SHALL reference valid entities.

Invalid:

```text
UnknownEntity

supports

Decision
```

---

# 10. Relationship Direction Validation

Each relationship SHALL preserve defined direction.

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

unless explicitly defined.

---

# 11. Relationship Cardinality Validation

Relationship cardinality SHALL comply with definition.

Example:

```text
part_of

N → 1
```

Invalid:

```text
Part

part_of

Multiple unrelated parents
```

unless supported.

---

# 12. Metadata Validation

## RULE-VAL-020

Ontology objects SHALL include:

```yaml
id:
type:
version:
status:
```

---

# 13. Provenance Validation

## RULE-VAL-021

Knowledge objects SHALL define provenance.

Required:

```yaml
source:
origin:
timestamp:
```

---

# 14. Schema Validation

## RULE-VAL-030

All ontology objects SHALL conform to registered schema.

Validation SHALL check:

- Required fields
- Field types
- Allowed values
- Constraints

---

# 15. Semantic Validation

## RULE-VAL-040

Relationship meaning SHALL match ontology definition.

Invalid:

```text
trusted_by

used as

authorized_by
```

---

# 16. Capability Validation

## RULE-VAL-050

Capabilities SHALL define:

```yaml
name:
description:
interface:
requirements:
```

---

# 17. Policy Validation

## RULE-VAL-060

Policies SHALL define:

```yaml
authority:
scope:
version:
effective_period:
```

---

# 18. Constraint Validation

## RULE-VAL-061

Constraints SHALL define:

```yaml
target:
boundary:
evaluation:
```

---

# 19. Federation Validation

## RULE-VAL-070

Federated entities SHALL define:

```yaml
node_id:
trust_domain:
identity:
```

---

# 20. Replica Validation

## RULE-VAL-071

Replicated entities SHALL preserve:

```yaml
source_identity:
replication_version:
provenance:
```

---

# 21. Synchronization Validation

## RULE-VAL-072

Synchronization relationships SHALL define:

```yaml
consistency_model:
sync_scope:
```

---

# 22. Validation Severity

Validation results SHALL classify:

| Level | Meaning |
|---|---|
| ERROR | Registration blocked |
| WARNING | Registration allowed |
| INFO | Advisory |

---

# 23. Validation Result Schema

Validation output SHALL contain:

```yaml
status:
entity:
violations:
warnings:
timestamp:
validator_version:
```

---

# 24. Registration Rules

Only objects satisfying:

```text
Validation Status = PASS
```

MAY enter:

- Knowledge Graph
- Semantic Registry
- Federation Registry

---

# 25. Runtime Validation

Runtime components MAY validate:

- Incoming events
- External knowledge
- Plugin metadata
- Agent messages
- Federation updates

---

# 26. Self-Healing Integration

Validation failures MAY trigger:

```text
ValidationFailedEvent
```

SelfHealing MAY attempt:

- Metadata repair
- Schema migration
- Reference correction

---

# 27. Determinism

For identical:

- Input
- Schema
- Ruleset

Validation result SHALL be identical.

---

# 28. Security Constraints

Validation engines SHALL NOT:

- Grant permissions
- Modify authority
- Override policies
- Remove constraints

---

# 29. Cross References

Related:

- Inference Rules
- Consistency Rules
- Provenance Rules
- Federation Rules
- Ontology Schema

Referenced:

- RFC-0263 SH-3 Architecture Intelligence Architecture
- RFC-0264 Meta Governance Architecture
- RFC-0269 Semantic Intelligence Layer Architecture

---

# 30. Summary

The SH-3 Ontology Validation Rules define the formal verification
framework for ontology objects.

They ensure that entities, relationships, metadata, schemas, and
federation objects conform to SH-3 specifications before entering the
trusted semantic ecosystem.

Validation provides the foundation for reliable Knowledge Graph
operation, autonomous reasoning, and production-grade semantic
intelligence.