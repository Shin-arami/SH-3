# RFC-0232

**Title:** Consensus Architecture

**Document ID:** RFC-0232

**Version:** 1.0

**Status:** Accepted

**Category:** Collective Intelligence Architecture

**Layer:** Collective Intelligence / Consensus

**Target:**

```text
architecture/consensus/
```

---

# Abstract

This RFC defines the SH-3 Consensus Architecture (CSA).

The Consensus Architecture establishes a deterministic framework for transforming one or more validated candidate proposals into a formally accepted collective decision within the SH-3 AI Operating System Framework.

Consensus is the governance-aware process by which participating agencies evaluate candidate agreements using evidence, policy, authority, objectives, operational constraints, and trust relationships.

Consensus is not equivalent to voting. Voting is one possible decision mechanism.

The architecture provides:

- candidate evaluation
- consensus protocol execution
- decision finalization
- dissent recording
- decision publication
- consensus observability

Every consensus cycle SHALL be:

- deterministic
- explainable
- traceable
- auditable
- reproducible
- policy-compliant

This document is normative.

---

# Motivation

Negotiation answers:

```text
Which candidate agreements are acceptable?
```

Consensus answers:

```text
Which candidate becomes the official collective decision?
```

Consensus transforms candidate agreements into authoritative organizational decisions.

---

# Goals

The architecture SHALL provide:

- deterministic collective decision-making
- governance-aware approval
- evidence-based evaluation
- transparent decision publication
- dissent preservation
- reproducible outcomes

---

# Non-Goals

The architecture SHALL NOT:

- replace Decision Architecture
- replace Negotiation Architecture
- generate new proposals
- bypass governance policies

---

# Architecture

```text
Negotiation Candidates

↓

Eligibility Validation

↓

Evidence Review

↓

Consensus Protocol

↓

Decision Adoption

↓

Publication

↓

Execution
```

---

# Core Components

| Component | Responsibility |
|------------|----------------|
| Consensus Manager | Consensus lifecycle |
| Candidate Evaluator | Candidate assessment |
| Protocol Manager | Consensus protocol execution |
| Decision Recorder | Decision persistence |
| Dissent Registry | Record minority positions |
| Publication Manager | Publish approved decisions |
| Consensus Monitor | Runtime monitoring |

---

# Consensus Model

Every consensus SHALL define:

```text
consensus_id

participants

candidate_set

selected_candidate

protocol

decision_state

confidence

metadata
```

---

# Consensus Protocols

The architecture SHALL support one or more of:

```text
Unanimous Agreement

Qualified Majority

Simple Majority

Weighted Voting

Authority-Based Approval

Evidence-Based Selection

Policy-Based Selection

Hybrid Consensus
```

Protocol selection SHALL be explicit and versioned.

---

# Candidate Evaluation

Each candidate SHALL be evaluated using:

- governance compliance
- mission alignment
- supporting evidence
- operational feasibility
- resource efficiency
- expected utility
- risk profile
- explainability

Evaluation SHALL be deterministic.

---

# Eligibility Validation

Before consensus begins, the architecture SHALL validate:

- participant authorization
- protocol compatibility
- candidate completeness
- policy compliance
- federation membership

Validation failures SHALL terminate the consensus cycle.

---

# Dissent Management

Participants MAY record dissenting opinions.

Every dissent SHALL include:

```text
participant

reason

supporting evidence

recommended alternative
```

Dissent records SHALL remain immutable after publication.

---

# Decision Publication

Approved decisions SHALL include:

```text
decision_id

selected_candidate

supporting evidence

protocol

participants

effective_time

version
```

Published decisions SHALL be immutable.

---

# Failure Handling

Consensus failures SHALL support:

- retry
- protocol change
- escalation
- renegotiation
- archival

Every failure SHALL be auditable.

---

# Agency Integration

Only authorized agencies MAY participate.

Reference:

RFC-0227 Agency Architecture

---

# Interaction Integration

Consensus SHALL use standardized interaction mechanisms.

Reference:

RFC-0228 Agent Interaction Architecture

---

# Federation Integration

Federation SHALL define the collective trust domain.

Reference:

RFC-0229 Federation Architecture

---

# Coordination Integration

Consensus SHALL finalize coordinated mission plans.

Reference:

RFC-0230 Coordination Architecture

---

# Negotiation Integration

Consensus SHALL evaluate only validated negotiation candidates.

Reference:

RFC-0231 Negotiation Architecture

---

# Decision Integration

Consensus decisions MAY become inputs to local decision execution.

Reference:

RFC-0214 Decision Architecture

---

# Governance Integration

Every consensus SHALL comply with:

- Constitutional Governance
- Organizational Policies
- Federation Agreements

References:

- RFC-0204 Constitutional Governance Architecture
- RFC-0209 Autonomous Governance Architecture

---

# Event Integration

Consensus events:

```text
ConsensusStarted

CandidateValidated

ConsensusReached

ConsensusRejected

DecisionPublished

DissentRecorded

ConsensusArchived
```

Events SHALL integrate with:

RFC-0152 Event Bus Architecture

---

# Security Integration

The architecture SHALL enforce:

- participant authentication
- authorization
- integrity verification
- audit logging

Reference:

RFC-0169 Security Architecture

---

# Observability Integration

Telemetry SHALL expose:

```text
consensus_count

consensus_latency

protocol_usage

decision_quality

dissent_rate

consensus_success_rate
```

Reference:

RFC-0171 Observability Architecture

---

# Testing Requirements

The architecture SHALL support:

- protocol tests
- eligibility validation tests
- publication tests
- governance compliance tests
- deterministic consensus tests

Reference:

RFC-0172 Testing Architecture

---

# Thread Model

The Consensus Architecture SHALL support concurrent:

- candidate evaluation
- protocol execution
- decision publication
- dissent recording
- monitoring

Reference implementation SHALL be:

- deterministic
- thread-safe
- event-driven
- lock-efficient

---

# Performance Metrics

```text
consensus_latency

candidate_evaluation_time

publication_latency

decision_accuracy

protocol_efficiency

collective_decision_quality
```

---

# Performance Objectives

The architecture should optimize for:

- reliable collective decisions
- transparent governance
- efficient protocol execution
- deterministic outcomes
- scalable organizational decision-making

---

# Future Work

Potential enhancements:

- Byzantine fault-tolerant consensus
- reputation-aware consensus
- adaptive protocol selection
- probabilistic consensus analysis
- cross-federation consensus

---

# References

- RFC-0231 Negotiation Architecture
- RFC-0230 Coordination Architecture
- RFC-0229 Federation Architecture
- RFC-0228 Agent Interaction Architecture
- RFC-0227 Agency Architecture
- RFC-0214 Decision Architecture
- RFC-0209 Autonomous Governance Architecture
- RFC-0204 Constitutional Governance Architecture
- RFC-0172 Testing Architecture
- RFC-0171 Observability Architecture
- RFC-0169 Security Architecture
- RFC-0152 Event Bus Architecture

---

# End of RFC-0232