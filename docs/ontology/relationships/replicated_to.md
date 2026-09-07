# SH-3 Relationship: replicated_to

Version: 1.0.0
Status: Stable
Category: Ontology Relationship
Relationship ID: REL-0602
Canonical Name: replicated_to
Predicate: replicated_to
Inverse Predicate: replicated_from
Author: SH-3 Architecture Working Group

---

# 1. Overview

The **replicated_to** relationship represents the canonical semantic
association in which an entity, state, knowledge, model, or artifact is
copied and materialized into another entity.

Replication creates an additional representation of an existing entity
while preserving source identity and provenance.

Unlike **synchronized_with**, which maintains coordinated consistency,
**replicated_to** represents the creation or maintenance of a replica.

---

# 2. Purpose

The replicated_to relationship enables:

- Data replication
- Knowledge distribution
- Memory replication
- Model distribution
- Disaster recovery
- Federation scalability
- Runtime state backup
- Distributed availability

Every replica SHALL preserve source provenance.

---

# 3. Canonical Definition

A subject **replicated_to** an object when the subject creates or
maintains a replicated representation within the object.

The replica MAY be:

- Full
- Partial
- Incremental
- Versioned
- Cached
- Derived

---

# 4. Characteristics

The **replicated_to** relationship SHALL be:

- Directed
- Data-oriented
- Traceable
- Versioned
- Machine readable
- Deterministic

Replication SHALL preserve lineage.

---

# 5. Relationship Signature

```text
Source Entity

replicated_to

Replica Entity
```

---

# 6. Semantic Meaning

The source entity provides content or state that is materialized within
the target entity.

Replication MAY apply to:

- Data
- Knowledge
- Memory
- Models
- Configuration
- Runtime state
- Artifacts

Replication SHALL NOT imply active synchronization.

---

# 7. Inverse Relationship

```text
Replica Entity

replicated_from

Source Entity
```

The inverse relationship SHALL preserve replication semantics.

---

# 8. Multiplicity

Supported cardinalities include:

- 1 → 1
- 1 → N
- N → N

A source MAY have multiple replicas.

---

# 9. Valid Examples

## Memory

```text
LongTermMemory

replicated_to

FederatedMemoryNode
```

---

## Knowledge Graph

```text
KnowledgeGraph

replicated_to

RemoteKnowledgeStore
```

---

## Model Distribution

```text
FoundationModel

replicated_to

InferenceNode
```

---

## Runtime State

```text
RuntimeState

replicated_to

BackupStorage
```

---

## Configuration

```text
PolicyConfiguration

replicated_to

FederationNode
```

---

# 10. Invalid Examples

The following SHOULD NOT use **replicated_to**.

```text
Agent

replicated_to

Agent

(as collaboration)
```

Use **synchronized_with**.

---

```text
Service

replicated_to

Capability
```

Use **provides**.

---

```text
Policy

replicated_to

Runtime

(as enforcement)
```

Use **governed_by**.

---

# 11. Replication Semantics

Replication MAY define:

- Replication strategy
- Frequency
- Version
- Consistency model
- Conflict policy
- Storage location
- Retention policy

Replication metadata SHALL remain observable.

---

# 12. Replication Models

Supported models MAY include:

- Full replication
- Incremental replication
- Event-based replication
- Snapshot replication
- Stream replication

Replication strategy SHALL be explicit.

---

# 13. Registry Integration

The replicated_to relationship SHALL integrate with:

- FED Registry
- MEM Registry
- KG Registry
- MOD Registry
- XRF Registry

Metadata MAY include:

```yaml
source:
replica:
version:
strategy:
timestamp:
consistency:
retention:
```

---

# 14. Federation

Federated SH-3 systems SHALL preserve:

- Source identity
- Replica identity
- Provenance chain
- Version information
- Trust relationship

Replicated entities SHALL remain attributable.

---

# 15. Constraints

The **replicated_to** relationship SHALL:

- Preserve provenance
- Support distributed availability
- Support recovery
- Support scalability
- Remain implementation independent

The relationship SHALL NOT imply:

- Synchronization
- Trust
- Ownership
- Execution

---

# 16. Relationship Comparison

| Relationship | Meaning |
|--------------|---------|
| synchronized_with | Maintains coordinated state |
| replicated_to | Creates a replica |
| trusted_by | Establishes trust |
| derived_from | Creates semantic lineage |
| references | Creates a link |

---

# 17. Examples

## Distributed Knowledge

```text
CentralKnowledgeBase

replicated_to

RegionalKnowledgeBase

↓

RegionalKnowledgeBase

synchronized_with

CentralKnowledgeBase
```

---

## AI Model Deployment

```text
TrainingModel

replicated_to

InferenceRuntime
```

---

## Disaster Recovery

```text
RuntimeState

replicated_to

RecoveryStorage
```

---

# 18. Reasoning Rules

Reasoning engines MAY infer replica lineage.

```text
Source

replicated_to

ReplicaA

ReplicaA

replicated_to

ReplicaB

↓

ReplicaB

derived_from

Source
```

Replication chains SHALL preserve original provenance.

---

# 19. Cross References

Related concepts:

- Federation
- Replica
- Memory
- Knowledge
- Model
- Runtime State
- Storage

Related relationships:

- synchronized_with
- trusted_by
- derived_from
- references

Referenced specifications:

- Federation Architecture
- Distributed Intelligence Architecture
- Persistence Architecture
- Memory Architecture
- RFC-0265 Federation Architecture
- RFC-0266 Collective Intelligence Architecture

---

# 20. Summary

The **replicated_to** relationship defines the canonical semantic
association between an original entity and its distributed replica
within the SH-3 Ontology.

It establishes the foundation for distributed knowledge, memory
sharing, model deployment, runtime recovery, and federation scalability
while preserving provenance, identity, and implementation-independent
semantics.