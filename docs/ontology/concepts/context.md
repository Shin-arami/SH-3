# SH-3 Concept: Context

Version: 1.0.0
Status: Stable
Category: Ontology Concept
Semantic ID: SEM-CONCEPT-0001
Canonical Name: Context
Author: SH-3 Architecture Working Group

---

# 1. Overview

Context is the canonical semantic concept representing the environment
under which information is interpreted, decisions are made, and
capabilities are executed.

Within SH-3, every semantic interpretation SHALL occur within one or
more contexts.

Context modifies interpretation but SHALL NOT modify the canonical
meaning of a concept.

---

# 2. Purpose

The Context concept provides:

- Semantic interpretation
- Execution environment
- Decision scope
- Constraint evaluation
- Capability selection
- Knowledge qualification
- Policy applicability

Every semantic artifact SHOULD reference an applicable context.

---

# 3. Canonical Definition

Context is the complete set of conditions that influence the semantic
interpretation of an entity, relationship, event, capability, or
decision.

A context SHALL provide information required to correctly interpret a
semantic object without altering its canonical definition.

---

# 4. Characteristics

A Context SHALL be:

- Explicit
- Immutable during evaluation
- Strongly typed
- Versioned
- Machine readable
- Human readable

---

# 5. Context Model

```
Context

↓

Environment

↓

Constraints

↓

Semantic Interpretation

↓

Decision

↓

Action
```

---

# 6. Core Properties

Every Context SHALL define:

```yaml
semantic_id:
context_id:
type:
scope:
status:
version:
metadata:
```

---

# 7. Context Categories

SH-3 defines the following canonical context categories.

## Runtime Context

Execution environment.

Examples:

- Scheduler
- Pipeline
- Execution Session

---

## Mission Context

Mission objectives.

Examples:

- Planning
- Recovery
- Optimization

---

## User Context

Information associated with a user or operator.

Examples:

- Preferences
- Permissions
- Locale

---

## Security Context

Security state.

Examples:

- Identity
- Trust
- Authorization

---

## Federation Context

Distributed collaboration state.

Examples:

- Federation ID
- Node Identity
- Trust Domain

---

## Temporal Context

Time-dependent interpretation.

Examples:

- Timestamp
- Deadline
- Validity Window

---

## Environmental Context

External operating conditions.

Examples:

- Hardware
- Network
- Platform
- Resources

---

# 8. Relationships

Context commonly participates in the following relationships.

```
Context

uses

Policy

Context

qualifies

Knowledge

Context

constrains

Capability

Context

interprets

Event

Context

supports

Decision
```

Relationship semantics are defined in
`docs/ontology/relationships.md`.

---

# 9. Constraints

A Context SHALL:

- Have a unique semantic identifier
- Define a clear scope
- Remain internally consistent
- Be available throughout semantic evaluation

Context SHALL NOT redefine canonical concepts.

---

# 10. Lifecycle

```
Created

↓

Validated

↓

Active

↓

Deprecated

↓

Archived
```

Historical context definitions SHALL remain accessible.

---

# 11. Registry Integration

The Context concept SHALL be registered in:

- SEM Registry

It MAY reference:

- CAP Registry
- EVT Registry
- MOD Registry
- XRF Registry

---

# 12. Reasoning

Reasoning engines SHALL evaluate Context before applying inference
rules.

Typical reasoning flow:

```
Knowledge

↓

Context Resolution

↓

Constraint Evaluation

↓

Inference

↓

Decision
```

---

# 13. Examples

## Runtime Example

```yaml
context:
  type: runtime
  scheduler: priority
  execution_mode: parallel
```

---

## Mission Example

```yaml
context:
  type: mission
  objective: recovery
  priority: high
```

---

## Federation Example

```yaml
context:
  type: federation
  federation_id: fed-001
  trust_level: verified
```

---

# 14. Cross References

Related concepts:

- Event
- Capability
- Policy
- Knowledge
- Mission
- Runtime

Referenced specifications:

- RFC-0269 Semantic Intelligence Layer
- RFC-0271 General Intelligence
- Semantic Model
- Relationships
- Reasoning

---

# 15. Summary

Context is the canonical semantic concept that defines the conditions
under which semantic interpretation occurs within the SH-3 AI Operating
System Framework.

It provides the foundation for context-aware reasoning, capability
selection, policy evaluation, and intelligent decision making while
preserving the canonical meaning of all semantic concepts.