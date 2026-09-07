# MOD-0808

# SH-3 Canonical Decision Schema

**Model ID:** MOD-0808

**Version:** 1.0

**Status:** Accepted

**Category:** Canonical Data Model

**Layer:** Decision Intelligence

**Target**

```text
docs/models/
```

---

# Abstract

This specification defines the canonical Decision Schema for the SH-3 AI Operating System Framework.

A Decision represents the result of evaluating available alternatives under a given Context while considering Goals, Policies, Knowledge, Risks, Capabilities, Constraints, and Utility.

Every significant action performed by SH-3 SHALL be traceable to a Decision object.

This document is normative.

---

# Purpose

The Decision Schema provides:

- canonical decision representation
- explainable decision making
- utility evaluation
- policy compliance
- risk assessment
- alternative comparison
- execution traceability

---

# Scope

This schema SHALL be used by:

- Decision Engine
- Planner
- Executive Controller
- Mission Engine
- Workflow Engine
- Policy Engine
- Semantic Intelligence
- Universal Intelligence

---

# Design Principles

## Explainable

Every Decision SHALL preserve the reasoning process.

---

## Utility Driven

Decisions SHALL maximize expected utility.

---

## Policy Governed

Decisions SHALL comply with applicable Policies.

---

## Context Aware

Decisions SHALL evaluate the active Context.

---

## Deterministic

Equivalent inputs SHOULD produce equivalent decisions.

---

# Canonical Decision Structure

| Field | Type | Required | Description |
|---------|------|:-------:|-------------|
| decision_id | UUID | ✓ | Global identifier |
| name | String | ✓ | Decision name |
| description | String | | Human-readable description |
| context_id | UUID | ✓ | Context reference |
| mission_id | UUID | | Mission reference |
| goal_id | UUID | ✓ | Goal reference |
| policy_ids | Array | ✓ | Applied policies |
| capability_ids | Array | | Candidate capabilities |
| knowledge_refs | Array | | Referenced Knowledge Objects |
| alternatives | Array | ✓ | Candidate alternatives |
| selected_alternative | Object | ✓ | Selected option |
| utility_score | Float | ✓ | Expected utility |
| confidence | Float | ✓ | Confidence score |
| risk | Object | | Risk assessment |
| constraints | Object | | Evaluated constraints |
| rationale | Object | ✓ | Explainable reasoning |
| status | Enum | ✓ | Lifecycle state |
| created_at | RFC3339 | ✓ | Creation timestamp |
| decided_at | RFC3339 | | Decision time |
| metadata | Object | | Additional metadata |

---

# Decision Types

Supported decision categories:

```text
Planning

Execution

Mission

Capability

Workflow

Policy

Resource

Scheduling

Optimization

Recovery

Learning

Federation
```

---

# Lifecycle

```text
Proposed

↓

Evaluating

↓

Validated

↓

Approved

↓

Executed

↓

Reviewed

↓

Archived
```

---

# Alternative Model

Each alternative SHALL define:

| Field | Description |
|---------|-------------|
| alternative_id | Unique identifier |
| description | Candidate action |
| expected_utility | Utility score |
| estimated_cost | Expected cost |
| estimated_risk | Estimated risk |
| confidence | Confidence |

---

# Utility Model

Utility MAY consider:

```text
goal_achievement

resource_efficiency

execution_time

quality

cost

risk

policy_compliance

knowledge_gain

user_value
```

Overall utility SHOULD be normalized to:

```text
0.0 – 1.0
```

---

# Risk Model

Risk MAY include:

```text
technical

operational

security

privacy

compliance

mission

semantic
```

Each risk SHOULD define:

- severity
- likelihood
- mitigation

---

# Constraints

Decision constraints MAY include:

```text
time

cost

resource

policy

security

performance

legal
```

---

# Explainability

The rationale SHALL preserve:

```text
evaluated_alternatives

selection_reason

utility_breakdown

policy_results

knowledge_used

risk_summary
```

---

# Decision Events

Decision lifecycle SHALL emit:

```text
DecisionCreated

DecisionEvaluated

DecisionApproved

DecisionRejected

DecisionExecuted

DecisionReviewed
```

---

# Validation Rules

A valid Decision SHALL:

- define a unique identifier
- reference a Goal
- reference a Context
- define at least one alternative
- define a selected alternative
- define utility
- define confidence

---

# Security

Decisions SHALL support:

- authentication
- authorization
- integrity verification
- immutable audit logging

Sensitive decisions SHOULD support encryption.

---

# Observability

Decision telemetry SHALL expose:

```text
decision_id

utility_score

confidence

evaluation_time

alternative_count

selected_alternative

status
```

---

# Compatibility

Decision schema evolution SHALL preserve backward compatibility whenever practical.

Breaking structural changes SHALL increment the major version.

---

# References

- RFC-0255 Decision Utility Architecture
- RFC-0257 Mission Execution Context Architecture
- RFC-0258 Executive Control Architecture
- RFC-0261 SH-3 Architecture Framework
- RFC-0264 SH-3 Meta Governance Architecture
- RFC-0271 General Intelligence Architecture
- RFC-0272 Universal Intelligence Architecture
- MOD-0803 Mission Schema
- MOD-0804 Knowledge Schema
- MOD-0805 Universal Context Schema
- MOD-0806 Policy Schema
- MOD-0807 Goal Schema

---

# End of MOD-0808