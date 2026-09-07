# SH-3 Ontology Provenance Schema

Version: 1.0.0
Status: Stable
Category: Ontology Schema
Schema ID: SCH-0400
Author: SH-3 Architecture Working Group

---

# 1. Overview

The SH-3 Ontology Provenance Schema defines the canonical structure for
tracking the origin, creation process, transformation history, and
verification context of semantic objects.

Provenance applies to:

- Entities
- Relationships
- Knowledge Objects
- Inference Results
- Decisions
- Memories
- Federation Data

---

# 2. Purpose

The Provenance Schema provides:

- Source traceability
- Knowledge lineage
- Audit support
- Explainable reasoning
- Trust evaluation
- Self-healing diagnostics

---

# 3. Provenance Model

Canonical structure:

```text
Provenance

├── Origin
├── Creator
├── Creation Context
├── Transformation History
├── Verification
├── Lineage
└── Audit
```

---

# 4. Provenance Schema

Canonical format:

```yaml
provenance:

  source:

  origin:

  creator:

  created_at:

  transformation:

  lineage:

  verification:

  audit:
```

---

# 5. Source Definition

Required for external knowledge.

```yaml
source:
```

Defines original information source.

Example:

```yaml
source:

  type:
    internal

  identifier:
    knowledge_repository
```

---

# 6. Origin Definition

Required:

```yaml
origin:
```

Defines initial creation location.

Example:

```yaml
origin:

  node:
    sh3.core.node01

  domain:
    cognition
```

---

# 7. Creator Definition

Optional:

```yaml
creator:
```

Defines the creator entity.

Example:

```yaml
creator:

  type:
    Agent

  id:
    planner_agent
```

---

# 8. Creation Timestamp

Required:

```yaml
created_at:
```

Format:

```yaml
created_at:
  ISO-8601 timestamp
```

---

# 9. Transformation History

Optional:

```yaml
transformation:
```

Records modifications.

Structure:

```yaml
transformation:

  action:

  actor:

  timestamp:

  reason:
```

---

# 10. Lineage Definition

Required for derived knowledge.

```yaml
lineage:
```

Defines parent relationships.

Example:

```yaml
lineage:

  derived_from:

    - entity_a

    - entity_b
```

---

# 11. Verification Section

Optional:

```yaml
verification:
```

Defines validation state.

Example:

```yaml
verification:

  status:
    verified

  validator:
    ontology_validator

  confidence:
    0.95
```

---

# 12. Audit Section

Optional:

```yaml
audit:
```

Defines operational history.

Example:

```yaml
audit:

  events:

    - created

    - validated

    - replicated
```

---

# 13. Inference Provenance

Inference results SHALL include:

```yaml
inference:

  rule_id:

  input_entities:

  confidence:

  engine:
```

---

# 14. Decision Provenance

Autonomous decisions SHALL include:

```yaml
decision:

  goal:

  context:

  reasoning_chain:

  policies:

  constraints:
```

---

# 15. Memory Provenance

Memory objects SHOULD include:

```yaml
memory:

  acquisition:

  context:

  importance:

  expiration:
```

---

# 16. Federation Provenance

Federated objects SHALL include:

```yaml
federation:

  source_node:

  transfer_history:

  trust_context:
```

---

# 17. Replication Provenance

Replicated objects SHALL include:

```yaml
replication:

  original_source:

  replica_chain:

  version:
```

---

# 18. Provenance Validation

Validator SHALL verify:

- Source existence
- Timestamp validity
- Lineage integrity
- Transformation consistency
- Identity preservation

---

# 19. Lineage Rules

Lineage SHALL be:

- Directed
- Traceable
- Immutable
- Version aware

---

# 20. Immutable History

Historical provenance SHALL NOT be deleted.

Allowed:

```text
append history
```

Not allowed:

```text
remove origin
```

---

# 21. Confidence Model

Provenance MAY contain:

```yaml
confidence:

reliability:

verification_level:
```

---

# 22. Provenance Conflict

Conflicting provenance SHALL create:

```text
ProvenanceConflictEvent
```

Example:

```text
Entity

created_by

AgentA


Entity

created_by

AgentB
```

without merge information.

---

# 23. SelfHealing Integration

SelfHealing MAY use provenance to identify:

- Fault origin
- Invalid transformation
- Corrupted knowledge
- Incorrect inference

---

# 24. Federation Compatibility

Across federation boundaries provenance SHALL preserve:

- Source identity
- Transfer history
- Trust context
- Validation status

---

# 25. Security Requirements

Provenance systems SHALL NOT:

- Forge origin
- Remove audit history
- Hide transformations
- Modify evidence

---

# 26. Cross References

Related:

- Entity Schema
- Relationship Schema
- Metadata Schema
- Federation Schema
- Provenance Rules

Referenced:

- RFC-0182 Memory Architecture
- RFC-0245 Self Reflection Architecture
- RFC-0265 Federation Architecture
- RFC-0269 Semantic Intelligence Layer Architecture

---

# 27. Summary

The SH-3 Ontology Provenance Schema defines the standard structure for
maintaining semantic lineage, auditability, and explainability across
the entire SH-3 ecosystem.

It ensures that every entity, relationship, inference result, memory,
and decision remains traceable from origin to current state.