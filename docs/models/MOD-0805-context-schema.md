# MOD-0805

# SH-3 Universal Context Schema

**Model ID:** MOD-0805

**Version:** 1.0

**Status:** Accepted

**Category:** Canonical Data Model

**Layer:** Universal Context

**Target**

```text
docs/models/
```

---

# Abstract

This specification defines the Universal Context Schema used throughout the SH-3 AI Operating System Framework.

A Context represents the complete execution state surrounding an operation, mission, decision, reasoning process, or intelligence activity.

The Universal Context Schema provides a canonical representation of purpose, intent, goals, knowledge, semantic understanding, resources, policies, execution state, and environmental information.

Every major component within SH-3 SHALL exchange information through this canonical context model.

This document is normative.

---

# Purpose

The Universal Context Schema provides:

- canonical execution context
- shared semantic understanding
- mission coordination
- planning context
- reasoning context
- decision context
- federation interoperability
- intelligence coordination

---

# Scope

This schema SHALL be used by:

- Runtime
- Kernel
- Planner
- Mission Engine
- Executive Controller
- Decision Engine
- Memory
- Semantic Intelligence
- Collective Intelligence
- Federation
- Universal Intelligence

---

# Design Principles

## Context First

Every operation SHALL execute within a Context.

---

## Shared Understanding

Context SHALL provide a common understanding across all components.

---

## Immutable Snapshot

Published Context objects SHOULD be treated as immutable snapshots.

---

## Explainable

Every decision SHALL reference its originating Context.

---

## Evolvable

Context SHALL support controlled evolution without breaking compatibility.

---

# Canonical Context Structure

| Field | Type | Required | Description |
|---------|------|:-------:|-------------|
| context_id | UUID | ✓ | Global context identifier |
| name | String | ✓ | Context name |
| purpose | Object | ✓ | Purpose |
| intent | Object | ✓ | Intent |
| mission | Object | | Mission |
| goals | Array | ✓ | Goals |
| environment | Object | ✓ | Execution environment |
| knowledge | Array | | Referenced Knowledge Objects |
| semantic_context | Object | ✓ | Semantic interpretation |
| memory | Object | | Memory references |
| capabilities | Array | | Available capabilities |
| resources | Object | | Resource allocation |
| participants | Array | | Participating agents/components |
| constraints | Object | | Operational constraints |
| policies | Array | | Applicable policies |
| risks | Array | | Known risks |
| assumptions | Array | | Execution assumptions |
| confidence | Float | ✓ | Overall confidence |
| execution_state | Enum | ✓ | Current state |
| correlation_id | UUID | | Workflow correlation |
| created_at | RFC3339 | ✓ | Creation timestamp |
| updated_at | RFC3339 | ✓ | Last update |
| metadata | Object | | Additional metadata |

---

# Execution States

Supported states:

```text
INITIALIZED

READY

PLANNING

EXECUTING

WAITING

PAUSED

COMPLETED

FAILED

ARCHIVED
```

---

# Environment Model

The environment MAY include:

```text
runtime

node

cluster

federation

network

platform

location

time

external_services
```

---

# Semantic Context

Semantic Context SHALL include:

```text
ontology

concepts

relationships

reasoning_scope

semantic_constraints
```

---

# Resource Model

Resources MAY include:

```text
cpu

memory

storage

gpu

network

energy

budget
```

---

# Constraint Model

Constraints MAY include:

```text
time

cost

security

privacy

policy

performance

resource

mission
```

---

# Risk Model

Each risk SHOULD define:

```text
risk_id

description

severity

likelihood

mitigation
```

---

# Capability References

Capabilities SHALL reference MOD-0802.

Example:

```text
planner

reasoner

workflow

memory

tool

executor
```

---

# Knowledge References

Knowledge SHALL reference MOD-0804.

Context SHALL reference Knowledge Objects rather than duplicate them.

---

# Mission References

Mission SHALL reference MOD-0803.

A Context MAY support multiple concurrent missions.

---

# Event Integration

Context SHALL be propagated using MOD-0801 Events.

Each event SHOULD reference:

```text
context_id

correlation_id
```

---

# Context Lifecycle

```text
Created

↓

Initialized

↓

Shared

↓

Updated

↓

Referenced

↓

Completed

↓

Archived
```

---

# Validation Rules

A valid Context SHALL:

- define a unique identifier
- include purpose
- include intent
- define execution state
- contain environment information
- define confidence
- preserve semantic consistency

---

# Security

Context SHALL support:

- authentication
- authorization
- integrity verification
- audit logging

Sensitive Context fields SHOULD support encryption.

---

# Observability

Context telemetry SHALL expose:

```text
context_id

execution_state

confidence

resource_usage

mission_count

capability_count

knowledge_count

last_updated
```

---

# Compatibility

Context schema evolution SHALL preserve backward compatibility whenever practical.

Breaking changes SHALL increment the major version.

---

# References

- RFC-0252 Purpose Architecture
- RFC-0253 Intent Management Architecture
- RFC-0254 Goal Management Architecture
- RFC-0257 Mission Execution Context Architecture
- RFC-0261 SH-3 Architecture Framework
- RFC-0269 Semantic Intelligence Layer Architecture
- RFC-0271 General Intelligence Architecture
- RFC-0272 Universal Intelligence Architecture
- MOD-0801 Event Schema
- MOD-0802 Capability Schema
- MOD-0803 Mission Schema
- MOD-0804 Knowledge Schema

---

# End of MOD-0805