# SH-3 Relationship: references

Version: 1.0.0
Status: Stable
Category: Ontology Relationship
Relationship ID: REL-0403
Canonical Name: references
Predicate: references
Inverse Predicate: referenced_by
Author: SH-3 Architecture Working Group

---

# 1. Overview

The **references** relationship represents the canonical semantic
association in which one entity cites, links to, or refers to another
entity without implying derivation, inference, dependency, execution, or
ownership.

The relationship provides lightweight semantic connectivity across the
SH-3 Knowledge Graph.

Unlike **derived_from**, no provenance is implied.

Unlike **inferred_from**, no logical conclusion is implied.

---

# 2. Purpose

The references relationship enables:

- Knowledge linking
- Documentation references
- Specification references
- Cross-module navigation
- Ontology connectivity
- Semantic indexing
- Explainable documentation
- Knowledge graph traversal

Referenced entities SHALL remain semantically independent.

---

# 3. Canonical Definition

A subject **references** an object when the subject identifies the
object as relevant contextual information.

The referenced entity SHALL remain unchanged.

The reference SHALL NOT imply semantic dependency.

---

# 4. Characteristics

The **references** relationship SHALL be:

- Directed
- Non-transitive
- Explainable
- Machine readable
- Versioned
- Deterministic

References SHALL preserve semantic independence.

---

# 5. Relationship Signature

```text
Referencing Entity

references

Referenced Entity
```

---

# 6. Semantic Meaning

The subject establishes a semantic link to another entity.

Reference MAY indicate:

- Citation
- Documentation
- Related concept
- External specification
- Supporting material
- Context

Reference SHALL NOT imply execution or ownership.

---

# 7. Inverse Relationship

```text
Referenced Entity

referenced_by

Referencing Entity
```

Both predicates SHALL preserve identical semantics.

---

# 8. Multiplicity

Supported cardinalities include:

- 1 → 1
- 1 → N
- N → N

Reference cycles MAY exist.

They SHALL remain explicitly represented.

---

# 9. Valid Examples

## Specification

```text
PluginAPI

references

ExtensionAPI
```

---

## RFC

```text
RFC-0269

references

RFC-0261
```

---

## Ontology

```text
Mission

references

Policy
```

---

## Documentation

```text
SDK Guide

references

Architecture Guide
```

---

## Knowledge Graph

```text
Concept

references

Ontology Term
```

---

# 10. Invalid Examples

The following SHOULD NOT use **references**.

```text
Summary

references

Source Document

(as provenance)
```

Use **derived_from**.

---

```text
Decision

references

Evidence

(as logical conclusion)
```

Use **inferred_from**.

---

```text
PlannerService

references

MemoryService

(as runtime interaction)
```

Use **uses**.

---

# 11. Reference Semantics

A reference MAY include metadata:

- Purpose
- Description
- Version
- Confidence
- Source
- Timestamp

Reference metadata SHALL NOT alter semantic meaning.

---

# 12. Registry Integration

The references relationship SHALL integrate with:

- DOC Registry
- RFC Registry
- SEM Registry
- KG Registry

Metadata MAY include:

```yaml
referencer:
reference:
purpose:
version:
timestamp:
```

---

# 13. Federation

Federated SH-3 systems SHALL preserve:

- Reference identity
- Version
- Provenance
- URI mapping

References SHALL remain resolvable across federation members.

---

# 14. Constraints

The **references** relationship SHALL:

- Preserve semantic independence
- Support knowledge navigation
- Support documentation linking
- Remain implementation independent

The relationship SHALL NOT imply:

- Derivation
- Inference
- Execution
- Ownership
- Dependency

---

# 15. Relationship Comparison

| Relationship | Meaning |
|--------------|---------|
| references | Contextual link |
| derived_from | Provenance |
| inferred_from | Logical conclusion |
| supports | Supporting evidence |

---

# 16. Examples

## Documentation

```text
Architecture Guide

references

SDK Guide
```

---

## RFC Network

```text
RFC-0269

references

RFC-0261

RFC-0261

references

RFC-0182
```

---

## Knowledge Graph

```text
Mission

references

Policy

Policy

references

Capability
```

---

# 17. Reasoning Rules

Reasoning engines SHALL treat **references** as a navigation
relationship.

The following inference SHALL NOT occur automatically:

```text
A references B

↓

A depends_on B
```

Reference SHALL remain informational.

---

# 18. Cross References

Related concepts:

- Document
- RFC
- Knowledge
- Ontology
- Specification
- Policy
- Capability

Related relationships:

- derived_from
- inferred_from
- supports
- referenced_by

Referenced specifications:

- Documentation Guide
- SDK
- Plugin API
- Extension API
- RFC Registry
- RFC-0269 Semantic Intelligence Layer

---

# 19. Summary

The **references** relationship defines the canonical semantic
association between an entity and another entity that it cites or links
to within the SH-3 Ontology.

It establishes the semantic foundation for documentation, knowledge
navigation, ontology connectivity, and cross-specification linkage while
preserving semantic independence and implementation-independent
architecture.