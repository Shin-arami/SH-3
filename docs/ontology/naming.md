# SH-3 Ontology Naming Convention

Version: 1.0
Status: Stable
Category: Ontology Foundation
Author: SH-3 Architecture Working Group

---

# 1. Overview

This document defines the official naming conventions used throughout
the SH-3 Ontology.

Consistent naming ensures:

- Semantic consistency
- Human readability
- Machine readability
- Cross-platform interoperability
- Deterministic identifier resolution

All ontology artifacts SHALL follow the conventions defined herein.

---

# 2. Naming Principles

The SH-3 naming system follows these principles.

- One concept, one canonical name
- Stable identifiers
- Immutable semantic identity
- Human-readable names
- Machine-readable identifiers
- Globally unique URIs
- Backward-compatible evolution

---

# 3. Canonical Name Rules

Every semantic concept SHALL define one canonical name.

Canonical names SHALL:

- Use singular nouns
- Be implementation independent
- Avoid abbreviations unless standardized
- Remain stable across versions

Examples:

```
Capability

Mission

Knowledge

Policy

Event

Context

Federation
```

---

# 4. Identifier Naming

Every ontology artifact SHALL possess a unique identifier.

Examples:

```
SEM-0701

CAP-0601

EVT-0801

MOD-1001
```

Identifiers SHALL never be reused.

Deprecated identifiers SHALL remain reserved.

---

# 5. URI Convention

Every ontology artifact SHOULD define a canonical URI.

General format:

```
<namespace>://<domain>/<resource>
```

Examples:

```
sem://planning/goal

cap://planning/create-plan

evt://runtime/started

mod://mission/base
```

URI segments SHALL use lowercase kebab-case.

---

# 6. Namespace Definitions

The following namespaces are reserved.

| Namespace | Purpose |
|-----------|---------|
| sem:// | Semantic concepts |
| cap:// | Capabilities |
| evt:// | Events |
| mod:// | Canonical models |
| ont:// | Ontologies |
| vocab:// | Vocabulary entries |
| rel:// | Relationship definitions |

Additional namespaces MAY be defined by future specifications.

---

# 7. Concept Naming

Concept names SHALL:

- Begin with an uppercase letter
- Use PascalCase
- Avoid implementation details
- Represent a single semantic concept

Examples:

```
Knowledge

Mission

Capability

RuntimeContext

SemanticGraph
```

---

# 8. Vocabulary Naming

Vocabulary entries SHOULD use:

- lowercase
- hyphen-separated words

Examples:

```
goal

knowledge

runtime

event-bus

semantic-graph
```

Vocabulary terms SHALL map to canonical concepts.

---

# 9. Ontology Naming

Ontology documents SHALL use descriptive names.

Examples:

```
core-ontology

runtime-ontology

event-ontology

knowledge-ontology

governance-ontology
```

File names SHALL use lowercase kebab-case.

---

# 10. Relationship Naming

Relationship names SHALL express direction.

Standard relationships include:

```
is_a

part_of

depends_on

implements

extends

uses

produces

consumes

governs

references
```

Relationship names SHALL remain stable.

---

# 11. Category Naming

Semantic categories SHALL use singular nouns.

Examples:

```
Concept

Capability

Event

Policy

Mission

Knowledge

Context

Resource
```

Plural forms SHOULD be avoided in identifiers.

---

# 12. File Naming

Ontology files SHALL use:

```
lowercase-kebab-case.md
```

Examples:

```
semantic-model.md

runtime-ontology.md

knowledge.md

event.md
```

Directory names SHALL also use lowercase kebab-case.

---

# 13. Version Naming

Ontology artifacts SHALL follow Semantic Versioning.

```
MAJOR.MINOR.PATCH
```

Example:

```
1.0.0
```

Major versions indicate incompatible semantic changes.

---

# 14. Metadata Naming

Common metadata fields SHALL use lowercase snake_case.

Example:

```yaml
semantic_id:
canonical_name:
preferred_label:
definition:
status:
version:
owner:
created:
updated:
```

Metadata field names SHALL remain stable.

---

# 15. Language Rules

The canonical ontology language is English.

Additional translations MAY be provided.

Translations SHALL NOT replace canonical names.

Example:

```
Canonical:

Mission

Translation:

ミッション
```

Reasoning SHALL always reference canonical identifiers.

---

# 16. Reserved Terms

The following identifiers are reserved.

```
Agent

Capability

Component

Context

Decision

Event

Federation

Goal

Knowledge

Memory

Mission

Node

Ontology

Plan

Policy

Runtime

Semantic

Service

Task
```

Reserved terms SHALL NOT be redefined.

---

# 17. Deprecated Names

Deprecated names SHALL:

- Remain resolvable
- Reference the replacement
- Preserve historical compatibility

Example:

```yaml
deprecated: true

replacement:
  Capability
```

Deprecated concepts SHALL NOT receive new semantics.

---

# 18. Validation Rules

Naming SHALL satisfy:

- Unique identifier
- Unique URI
- Canonical concept
- Stable version
- Valid namespace
- Approved category

Validation SHOULD be automated.

---

# 19. Governance

Naming changes SHALL require:

- Semantic review
- Ontology review
- Registry synchronization
- XRF update

Canonical names SHOULD remain unchanged whenever possible.

---

# 20. Summary

The SH-3 Ontology Naming Convention establishes a consistent,
machine-readable, and implementation-independent naming system for all
semantic artifacts.

It provides a unified foundation for identifiers, URIs, concepts,
vocabularies, ontologies, and relationships, ensuring long-term
stability, interoperability, and semantic consistency across the SH-3 AI
Operating System Framework.