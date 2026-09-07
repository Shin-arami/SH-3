# SH-3 Certification Levels Specification

Version:
1.0.0

Status:
Architecture Specification

Category:
Certification Levels

---

# 1. Purpose

This document defines the certification level model for SH-3.

Certification levels establish progressively stronger assurance requirements for:

- Validation
- Evidence
- Security
- Audit
- Governance
- Operational assurance
- Continuous compliance

---

# 2. Certification Level Principle

SH-3 certification assurance increases with system criticality, operational exposure, security risk, and required trust.

The level model is:

```text
Level 1
Basic Conformance
    ↓
Level 2
Validated Conformance
    ↓
Level 3
Production Assurance
    ↓
Level 4
Critical Assurance
```

A higher level includes the assurance requirements of all lower levels unless explicitly stated otherwise.

---

# 3. Certification Level Objectives

Certification levels provide a consistent method for determining:

```text
Required Controls

Required Evidence

Required Validation

Required Review

Required Audit

Required Security Assurance

Required Monitoring
```

---

# 4. Level Selection

The certification level must be selected according to the highest applicable assurance requirement.

Factors include:

```text
System Criticality

Security Exposure

Operational Impact

Data Sensitivity

Autonomy

External Exposure

Failure Consequence

Recovery Requirements
```

---

# 5. Level Non-Substitution

A lower certification level must not be used to avoid requirements applicable to a higher-risk subject.

---

# 6. Level Upgrade

A certification may be upgraded when additional assurance requirements are satisfied.

The upgrade process is:

```text
Current Certification
    ↓
Gap Analysis
    ↓
Additional Requirements
    ↓
Additional Evidence
    ↓
Additional Validation
    ↓
Review
    ↓
Level Upgrade
```

---

# 7. Level Downgrade

A certification level must not be downgraded merely to avoid unresolved findings.

Downgrade requires:

```text
Scope Analysis

Risk Assessment

Authority Approval

Updated Certification Scope
```

---

# 8. Level 1 Overview

Level 1 provides basic conformance assurance.

It establishes that the subject:

```text
Has a Defined Scope

Has Applicable Requirements

Provides Basic Evidence

Passes Required Basic Validation

Maintains Basic Traceability
```

---

# 9. Level 1 Scope

Level 1 is suitable for systems where:

```text
Operational Impact Is Limited

Security Exposure Is Limited

Failure Consequences Are Low

Basic Conformance Is Sufficient
```

---

# 10. Level 1 Requirements

Level 1 requires:

```text
Defined Certification Scope

Requirement Baseline

Basic Validation

Evidence Collection

Compliance Result

Basic Audit Trail
```

---

# 11. Level 1 Evidence

Required evidence should demonstrate:

```text
Requirement Applicability

Validation Execution

Validation Result

Basic Configuration
```

---

# 12. Level 1 Security

Level 1 security requires:

```text
Basic Identity

Basic Authorization

Basic Integrity Protection

Basic Security Review
```

---

# 13. Level 1 Audit

Level 1 requires:

```text
Audit Record

Requirement Traceability

Evidence Traceability

Certification Decision Record
```

---

# 14. Level 1 Review

A Level 1 review verifies:

```text
Scope

Requirements

Evidence

Results

Open Findings
```

---

# 15. Level 1 Decision

Level 1 certification may be issued when:

```text
Mandatory Requirements Are Satisfied

Required Evidence Exists

No Blocking Finding Exists

Required Review Is Complete
```

---

# 16. Level 1 Monitoring

Monitoring is primarily event-driven.

Material changes may trigger revalidation.

---

# 17. Level 2 Overview

Level 2 provides validated conformance assurance.

It adds stronger:

```text
Validation

Evidence

Security

Audit

Control Verification
```

---

# 18. Level 2 Scope

Level 2 is suitable for systems with:

```text
Meaningful Operational Use

Moderate Security Exposure

External Dependencies

Moderate Failure Impact
```

---

# 19. Level 2 Requirements

Level 2 includes all Level 1 requirements plus:

```text
Formal Validation Plan

Control Effectiveness Evaluation

Dependency Review

Security Validation

Formal Compliance Audit
```

---

# 20. Level 2 Evidence

Level 2 evidence should include:

```text
Detailed Test Results

Configuration Evidence

Dependency Evidence

Security Evidence

Audit Evidence
```

---

# 21. Level 2 Security

Level 2 requires:

```text
Access Control Validation

Security Testing

Dependency Security Review

Security Finding Management
```

---

# 22. Level 2 Audit

Level 2 requires a formal audit covering:

```text
Requirements

Controls

Validation

Evidence

Findings

Certification Decision
```

---

# 23. Level 2 Review

The review must verify that:

```text
Controls Are Implemented

Controls Are Effective

Evidence Is Sufficient

Findings Are Managed
```

---

# 24. Level 2 Decision

Level 2 certification may be issued only when:

```text
Mandatory Requirements Are Satisfied

Required Validation Is Complete

Critical Findings Are Closed

Required Security Review Is Complete
```

---

# 25. Level 2 Monitoring

Monitoring should detect:

```text
Material Configuration Change

Critical Dependency Change

Security Finding

Certification Drift
```

---

# 26. Level 3 Overview

Level 3 provides production assurance.

It establishes that the subject is suitable for sustained production operation under defined conditions.

---

# 27. Level 3 Scope

Level 3 is suitable for systems with:

```text
Production Deployment

Significant Operational Impact

Meaningful Security Exposure

Important External Interfaces

Operational Dependencies
```

---

# 28. Level 3 Requirements

Level 3 includes all Level 2 requirements plus:

```text
Production Validation

Operational Readiness

Security Assurance

Change Management

Recovery Validation

Continuous Compliance

Dependency Monitoring
```

---

# 29. Level 3 Production Validation

Production validation should verify:

```text
Deployment

Runtime

Monitoring

Failure Handling

Recovery

Operational Controls
```

---

# 30. Level 3 Evidence

Level 3 evidence should establish:

```text
Production Configuration

Deployment Integrity

Runtime Validation

Security Validation

Recovery Validation

Operational Evidence
```

---

# 31. Level 3 Security

Level 3 requires:

```text
Threat Monitoring

Security Monitoring

Incident Response

Secure Deployment

Dependency Monitoring

Configuration Security
```

---

# 32. Level 3 Audit

Level 3 audit should include:

```text
Operational Audit

Security Audit

Change Audit

Recovery Audit

Continuous Assurance Review
```

---

# 33. Level 3 Review

Level 3 review should evaluate:

```text
Production Risk

Operational Controls

Security Controls

Recovery

Monitoring

Open Findings
```

---

# 34. Level 3 Decision

Level 3 certification requires:

```text
Production Requirements Satisfied

Security Requirements Satisfied

Operational Readiness Confirmed

Recovery Validated

Critical Risks Controlled
```

---

# 35. Level 3 Monitoring

Level 3 requires continuous or periodic monitoring appropriate to risk.

Monitoring includes:

```text
Security

Configuration

Dependencies

Runtime

Operational Health

Compliance Drift
```

---

# 36. Level 4 Overview

Level 4 provides critical assurance.

It is the highest SH-3 certification level and is intended for systems where failure, compromise, or incorrect behavior may have severe consequences.

---

# 37. Level 4 Scope

Level 4 is suitable for systems with:

```text
Critical Operations

High Security Exposure

High Failure Consequence

High Autonomy

Critical Data

Critical External Interfaces
```

---

# 38. Level 4 Requirements

Level 4 includes all Level 3 requirements plus:

```text
Independent Assurance

Enhanced Security Review

Enhanced Evidence Integrity

Strong Separation of Duties

Continuous Assurance

Enhanced Recovery

Enhanced Governance
```

---

# 39. Level 4 Validation

Validation should use stronger assurance mechanisms.

Depending on the system, these may include:

```text
Independent Testing

Adversarial Testing

Formal Analysis

Failure Injection

Recovery Testing

Security Assessment
```

---

# 40. Level 4 Evidence

Level 4 evidence should provide:

```text
Strong Integrity

Strong Traceability

Independent Verification

Long-Term Retention

Reproducibility
```

---

# 41. Level 4 Security

Level 4 requires enhanced:

```text
Identity Assurance

Authorization

Cryptographic Integrity

Audit Protection

Threat Monitoring

Incident Response
```

---

# 42. Level 4 Audit

Level 4 requires independent audit appropriate to the certification scope.

The audit should evaluate:

```text
Architecture

Security

Compliance

Operations

Recovery

Governance

Certification Integrity
```

---

# 43. Level 4 Review

Review must provide strong independence and separation of duties.

The same actor should not control all critical certification decisions.

---

# 44. Level 4 Decision

Level 4 certification requires:

```text
All Critical Requirements Satisfied

Critical Risks Controlled

Independent Review Complete

Security Assurance Complete

Recovery Assurance Complete

Audit Complete
```

---

# 45. Level 4 Monitoring

Level 4 requires continuous assurance where technically and operationally feasible.

Monitoring should detect:

```text
Security Drift

Configuration Drift

Dependency Drift

Evidence Integrity Failure

Critical Runtime Change

Threat Changes
```

---

# 46. Level Comparison

The certification levels can be summarized as:

```text
Level 1
Conformance

Level 2
Validation

Level 3
Production Assurance

Level 4
Critical Assurance
```

---

# 47. Assurance Matrix

The minimum assurance progression is:

```text
Area                  L1       L2       L3       L4

Scope                 Basic    Formal   Formal   Critical
Requirements          Basic    Formal   Formal   Enhanced
Validation            Basic    Formal   Production Independent
Evidence               Basic    Detailed Production Enhanced
Security              Basic    Validated Continuous Enhanced
Audit                 Basic    Formal   Operational Independent
Review                Standard Formal   Strong   Independent
Monitoring            Event    Periodic Continuous Continuous
Recovery              Basic    Tested   Validated Enhanced
Governance             Basic    Formal   Strong   Enhanced
```

---

# 48. Level Inheritance

Higher levels inherit lower-level requirements.

Therefore:

```text
L4 ⊇ L3 ⊇ L2 ⊇ L1
```

unless a formally approved certification profile defines an equivalent alternative control.

---

# 49. Alternative Controls

An alternative control may satisfy the intent of a requirement when:

```text
Equivalent Assurance Is Demonstrated

Risk Is Documented

Authority Approves

Traceability Is Preserved
```

---

# 50. Level Profile

A certification profile should define:

```text
Level

Scope

Applicable Requirements

Required Controls

Required Evidence

Required Validation

Required Review

Required Audit

Monitoring
```

---

# 51. Level Profile Versioning

Certification profiles must be versioned.

A profile change may require:

```text
Impact Analysis

Gap Analysis

Revalidation
```

for affected certifications.

---

# 52. Level Assignment

Level assignment must be recorded with:

```text
Certification ID

Level

Reason

Scope

Authority

Effective Date
```

---

# 53. Level Evidence

The evidence package must demonstrate why the assigned level is appropriate.

---

# 54. Level Misclassification

If a subject is discovered to have been certified at an insufficient level, the certification authority must perform:

```text
Risk Assessment

Impact Analysis

Level Reassessment

Additional Validation
```

---

# 55. Level Escalation

Escalation is required when:

```text
Risk Increases

Operational Scope Expands

Security Exposure Increases

Autonomy Increases

Failure Consequence Increases
```

---

# 56. Level Reassessment

Level reassessment may be triggered by:

```text
Material Architecture Change

Production Deployment

New External Interface

New Data Class

Security Incident

Regulatory Change

Autonomy Change
```

---

# 57. Level Change

A certification level change must preserve the historical record.

The system must retain:

```text
Previous Level

New Level

Reason

Evidence

Decision Authority

Effective Date
```

---

# 58. Level Expiration

Certification level validity may expire according to:

```text
Certification Policy

Risk

Subject Change Rate

Evidence Freshness
```

---

# 59. Level Renewal

Renewal must verify that the current subject still satisfies the assigned level.

Renewal should reassess:

```text
Scope

Requirements

Security

Operations

Dependencies

Risk
```

---

# 60. Level Suspension

A certification may be suspended when the required assurance level can no longer be demonstrated.

Triggers include:

```text
Critical Finding

Evidence Integrity Failure

Security Incident

Major Drift

Uncontrolled Risk
```

---

# 61. Level Revocation

A certification may be revoked when:

```text
Critical Nonconformity Exists

Certification Was Fraudulently Obtained

Trust Cannot Be Restored

Required Remediation Fails
```

---

# 62. Level Recovery

Suspended certification may be restored when:

```text
Root Cause Resolved

Required Controls Restored

Evidence Revalidated

Risk Reassessed

Authority Approves
```

---

# 63. Level Governance

Certification levels are governed by:

```text
Certification Authority

Compliance Policy

Security Policy

Architecture Governance
```

---

# 64. Level Security Gate

A level assignment must not exceed the demonstrated security assurance.

---

# 65. Level Evidence Gate

A level assignment must not exceed the assurance supported by available evidence.

---

# 66. Level Audit Gate

The required audit must be complete before certification at the applicable level is issued.

---

# 67. Level Review Gate

Required independent review must be complete before certification at levels requiring independence is issued.

---

# 68. Level Decision Gate

Certification decision authority must be appropriate to the assigned level.

---

# 69. Level Compliance Gate

All mandatory requirements for the assigned level must be satisfied.

---

# 70. Level Monitoring Gate

The monitoring model must be sufficient to detect material loss of assurance.

---

# 71. Level Determinism

Given equivalent:

```text
Subject

Scope

Requirements

Risk

Evidence

Validation
```

the level determination should be reproducible.

---

# 72. Level Traceability

Level assignment must be traceable to:

```text
Risk

Scope

Requirements

Evidence

Decision
```

---

# 73. Level Auditability

Every level change must be auditable.

---

# 74. Level Metrics

The certification system may track:

```text
Certification Count by Level

Upgrade Rate

Downgrade Rate

Suspension Rate

Revocation Rate

Renewal Rate

Finding Rate by Level
```

Metrics must not override formal level decisions.

---

# 75. Level Distribution

Organizations may maintain a distribution such as:

```text
L1: Development / Low Risk

L2: Validated Systems

L3: Production Systems

L4: Critical Systems
```

Actual classification remains subject to the certification authority.

---

# 76. Level Selection Anti-Patterns

The following are prohibited:

- Selecting a lower level solely to reduce validation effort
- Treating Level 1 as sufficient for a critical system
- Assigning Level 4 without required evidence
- Skipping mandatory inherited controls
- Ignoring level-triggering changes
- Downgrading after a critical finding without risk review
- Treating level assignment as permanent
- Claiming higher assurance without corresponding validation

---

# 77. Certification Level Events

The certification subsystem should emit typed events:

```text
CertificationLevelAssigned

CertificationLevelReviewed

CertificationLevelUpgradeRequested

CertificationLevelUpgraded

CertificationLevelDowngradeRequested

CertificationLevelDowngraded

CertificationLevelReassessmentRequired

CertificationLevelSuspended

CertificationLevelRestored

CertificationLevelRevoked
```

---

# 78. Level Process Contract

The level process requires:

```text
Explicit Level

Explicit Criteria

Explicit Scope

Explicit Evidence

Explicit Decision Authority

Explicit Effective Date
```

---

# 79. Certification Level Conformance

An implementation conforms to this specification when it supports:

```text
Level Definition

Level Assignment

Level Evaluation

Level Evidence

Level Review

Level Audit

Level Change

Level Monitoring
```

---

# 80. Final Level Model

The SH-3 certification level model is:

```text
L1
Basic Conformance
    ↓
L2
Validated Conformance
    ↓
L3
Production Assurance
    ↓
L4
Critical Assurance
```

Each level increases the strength of:

```text
Validation

Evidence

Security

Audit

Review

Monitoring

Governance
```

---

# 81. Final Definition

SH-3 Certification Levels provide a structured assurance hierarchy for determining how rigorously a subject must be evaluated before and during certification.

The model ensures that:

```text
Higher Risk
    →
Higher Assurance

Higher Criticality
    →
Stronger Controls

Higher Security Exposure
    →
Stronger Security Validation

Higher Failure Consequence
    →
Stronger Independent Assurance
```

Certification level therefore represents the minimum demonstrated assurance appropriate to the subject's risk, scope, operational context, and criticality.

---

# End of Document
