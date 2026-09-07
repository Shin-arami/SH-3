# SH-3 Ontology Consistency Rules

Version: 1.0.0
Status: Stable
Category: Ontology Rules
Rule Set ID: RULE-0200
Author: SH-3 Architecture Working Group

---

# 1. Overview

The SH-3 Ontology Consistency Rules define the semantic integrity
requirements for maintaining a valid Knowledge Graph.

Consistency Rules ensure that ontology entities, relationships, and
derived knowledge remain logically compatible.

The rules prevent:

- Contradictory relationships
- Invalid semantic combinations
- Impossible states
- Governance conflicts
- Federation inconsistencies

---

# 2. Purpose

Consistency Rules enable:

- Knowledge Graph validation
- Semantic error detection
- Automated repair
- Reliable reasoning
- Explainable intelligence
- Autonomous system stability

---

# 3. Core Principles

SH-3 consistency follows:

```text
Valid Ontology

+

Valid Relationships

+

Valid Constraints

=

Consistent Knowledge Graph
```

---

# 4. Rule Categories

| Category | Purpose |
|---|---|
| Entity Consistency | Entity validity |
| Relationship Consistency | Relationship compatibility |
| Governance Consistency | Policy integrity |
| Federation Consistency | Distributed integrity |
| Reasoning Consistency | Inference correctness |

---

# 5. Entity Consistency Rules

## RULE-CON-001

## Entity Identity Uniqueness

Condition:

```text
Entity ID exists
```

Requirement:

Each entity SHALL have a unique identifier.

Invalid:

```text
EntityA

ID: same

EntityB

ID: same
```

---

# 6. Entity Type Consistency

## RULE-CON-002

An entity SHALL have a stable ontology type.

Invalid:

```text
Entity

type: Service

type: Policy
```

without explicit version transition.

---

# 7. Relationship Consistency Rules

## RULE-CON-010

## Self Relationship Prevention

The following SHALL be invalid:

```text
A

part_of

A
```

unless explicitly defined as recursive ontology structure.

---

# 8. Contradictory Relationship Prevention

## RULE-CON-011

The following combination SHALL be invalid:

```text
A owns B

A belongs_to B
```

unless ownership semantics explicitly allow containment.

---

# 9. Relationship Direction Consistency

Each relationship SHALL preserve direction.

Invalid:

```text
A provides B

B provides A
```

without explicit bidirectional declaration.

---

# 10. Capability Consistency

## RULE-CON-020

Condition:

```text
A implements Capability
```

Requirement:

A SHALL provide required capability metadata.

---

Invalid:

```text
Component

implements

Capability
```

but no capability definition exists.

---

# 11. Dependency Consistency

## RULE-CON-030

Circular dependency SHALL be detected.

Invalid:

```text
A requires B

B requires C

C requires A
```

unless cycle is explicitly permitted.

---

# 12. Execution Consistency

## RULE-CON-040

Execution SHALL require capability availability.

Invalid:

```text
Agent

executes

Task
```

without:

```text
Agent

provides

RequiredCapability
```

---

# 13. Knowledge Consistency

## RULE-CON-050

## Provenance Requirement

Derived knowledge SHALL preserve origin.

Invalid:

```text
Knowledge

derived_from

Unknown
```

---

# 14. Inference Consistency

## RULE-CON-051

Inference SHALL NOT override explicit knowledge.

Example:

Explicit:

```text
A constrained_by SafetyPolicy
```

Inference:

```text
A unrestricted
```

Invalid.

---

# 15. Governance Consistency

## RULE-CON-060

Authorization SHALL NOT exceed governance scope.

Invalid:

```text
Agent

authorized_by

PermissionA


PermissionA

outside

GovernanceDomain
```

---

# 16. Constraint Consistency

## RULE-CON-061

Conflicting constraints SHALL be detected.

Invalid:

```text
ResourceLimit

max_cpu: 50%


ResourceLimit

max_cpu: 90%
```

without priority resolution.

---

# 17. Policy Consistency

Policies SHALL define:

- Scope
- Version
- Authority
- Effective period

Missing values SHALL trigger validation failure.

---

# 18. Federation Consistency

## RULE-CON-070

Replica identity SHALL preserve source.

Invalid:

```text
Replica

without

SourceIdentity
```

---

# 19. Synchronization Consistency

## RULE-CON-071

Synchronization SHALL define consistency model.

Required:

```yaml
consistency_model:
```

---

# 20. Trust Consistency

## RULE-CON-072

Trust SHALL have evaluation context.

Invalid:

```text
A trusted_by B
```

without:

```yaml
verification:
```

---

# 21. Version Consistency

All ontology objects SHALL include:

```yaml
version:
timestamp:
```

---

# 22. Conflict Resolution

When conflicts occur:

Priority order:

```text
Explicit Knowledge

>

Validated Policy

>

Derived Knowledge

>

Inference Result
```

---

# 23. Repair Rules

SelfHealing systems MAY repair:

- Missing metadata
- Invalid references
- Outdated versions
- Broken links

Repair SHALL preserve provenance.

---

# 24. Validation Result

Consistency validation SHALL return:

```yaml
status:
violations:
warnings:
affected_entities:
repair_actions:
```

---

# 25. Determinism

Given identical:

- Ontology
- Knowledge Graph
- Ruleset

Validation result SHALL remain identical.

---

# 26. Federation Compatibility

Consistency validation across federation SHALL preserve:

- Rule version
- Validation context
- Node identity
- Result provenance

---

# 27. Security Constraints

Validators SHALL NOT:

- Modify authority
- Grant permission
- Remove constraints
- Alter trust

---

# 28. Cross References

Related:

- Inference Rules
- Validation Rules
- Provenance Rules
- Federation Rules
- Knowledge Graph Architecture

Referenced:

- RFC-0263 SH-3 Architecture Intelligence Architecture
- RFC-0264 Meta Governance Architecture
- RFC-0265 Federation Architecture
- RFC-0269 Semantic Intelligence Layer Architecture

---

# 29. Summary

The SH-3 Ontology Consistency Rules define the semantic integrity
framework for Knowledge Graph correctness.

They provide automatic detection of contradictions, invalid states,
governance conflicts, and federation inconsistencies while preserving
determinism, explainability, and autonomous system reliability.