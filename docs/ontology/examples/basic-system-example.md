# SH-3 Ontology Example: Basic System

Version: 1.0.0
Status: Example
Category: Ontology Example
Example ID: EX-0100

---

# 1. Overview

This example demonstrates the minimum semantic structure of an SH-3
system using Ontology Entities.

The example represents a small autonomous SH-3 environment containing:

- System
- Components
- Services
- Capabilities
- Agent
- Memory
- Knowledge
- Policy

---

# 2. Semantic Graph

```text
SH-3 System

    |
    | contains
    |
    +----------------+
    |                |
 Component       Component
 EventBus        MemoryEngine

    |
    | provides
    |
 Service

    |
    | provides
    |
 Capability

    |
    | used_by
    |
 Agent

    |
    | creates
    |
 Memory

    |
    | produces
    |
 Knowledge

    |
    | governed_by
    |
 Policy
```

---

# 3. System Entity

```yaml
entity:

  id:
    sh3.system.example

  type:
    System

  name:
    SH-3 Example Intelligence System

  version:
    1.0.0

  status:
    active
```

---

# 4. Component Entities

## EventBus Component

```yaml
entity:

  id:
    sh3.component.event_bus

  type:
    Component

  name:
    SH-3 Event Bus

  version:
    1.0.0

  runtime:

    event_driven:
      true

    thread_safe:
      true
```

Relationship:

```text
System

contains

EventBus Component
```

---

## Memory Engine Component

```yaml
entity:

  id:
    sh3.component.memory_engine

  type:
    Component

  name:
    Memory Engine

  version:
    1.0.0
```

Relationship:

```text
System

contains

Memory Engine
```

---

# 5. Service Entity

Memory Service:

```yaml
entity:

  id:
    sh3.service.memory

  type:
    Service

  name:
    Memory Service

  version:
    1.0.0
```

Relationship:

```text
Memory Engine

implements

Memory Service
```

---

# 6. Capability Entity

Memory Retrieval Capability:

```yaml
entity:

  id:
    sh3.capability.memory_retrieval

  type:
    Capability

  name:
    Memory Retrieval Capability

  version:
    1.0.0
```

Relationship:

```text
Memory Service

provides

Memory Retrieval Capability
```

---

# 7. Agent Entity

Planner Agent:

```yaml
entity:

  id:
    sh3.agent.planner

  type:
    Agent

  name:
    Planner Agent

  version:
    1.0.0
```

Relationships:

```text
Planner Agent

has

Planning Capability
```

```text
Planner Agent

uses

Memory Service
```

---

# 8. Memory Entity

Decision Memory:

```yaml
entity:

  id:
    sh3.memory.decision001

  type:
    Memory

  name:
    Decision Experience Memory

  classification:

    type:
      Episodic
```

Relationship:

```text
Planner Agent

creates

Decision Memory
```

---

# 9. Knowledge Entity

Learned Knowledge:

```yaml
entity:

  id:
    sh3.knowledge.pattern001

  type:
    Knowledge

  name:
    Execution Pattern Knowledge

  confidence:

    score:
      0.95
```

Relationship:

```text
Memory

produces

Knowledge
```

---

# 10. Policy Entity

Execution Safety Policy:

```yaml
entity:

  id:
    sh3.policy.execution

  type:
    Policy

  name:
    Execution Safety Policy

  version:
    1.0.0
```

Relationship:

```text
Policy

governs

Agent
```

---

# 11. Complete Relationship Map

```text
System

contains

 ├── EventBus Component
 |
 └── Memory Component


Memory Component

implements

Memory Service


Memory Service

provides

Memory Retrieval Capability


Planner Agent

has

Planning Capability


Planner Agent

uses

Memory Service


Planner Agent

creates

Decision Memory


Decision Memory

produces

Knowledge


Execution Policy

governs

Planner Agent
```

---

# 12. Validation Example

The graph is valid because:

- Every entity has identity
- Relationships are typed
- Capabilities are separated from implementation
- Policies govern execution
- Memory preserves provenance
- Knowledge maintains confidence

---

# 13. SH-3 Principle Mapping

## Everything Event Driven

Implemented by:

```text
EventBus Component
```

---

## Everything Replaceable

Implemented by:

```text
Component

↓

Service Contract
```

---

## Everything Typed

Implemented by:

```text
Ontology Entity Type
```

---

## Everything Testable

Implemented by:

```text
Entity Boundary

+

Service Contract
```

---

# 14. Summary

This example demonstrates the minimum complete SH-3 semantic structure.

It shows how Systems, Components, Services, Capabilities, Agents,
Memory, Knowledge, and Policies combine into a coherent ontology graph.