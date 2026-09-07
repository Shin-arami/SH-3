# SH-3 Certification Audit Specification

Version:
1.0.0

Status:
Architecture Specification

Category:
Certification Audit

---

# 1. Purpose

This document defines the audit model for SH-3 certification.

The audit model establishes the controls required to verify that certification activities, evidence, findings, decisions, and lifecycle changes remain complete, traceable, authorized, and integrity protected.

The specification covers:

- Audit scope
- Audit records
- Audit trails
- Audit events
- Audit integrity
- Audit review
- Audit findings
- Audit evidence
- Audit retention
- Audit access
- Audit escalation
- Continuous audit

---

# 2. Audit Principle

SH-3 certification must be auditable from request through final lifecycle state.

The fundamental audit chain is:

```text
Request
    ↓
Scope
    ↓
Requirements
    ↓
Validation
    ↓
Evidence
    ↓
Findings
    ↓
Risk
    ↓
Review
    ↓
Decision
    ↓
Certification
    ↓
Monitoring
    ↓
Renewal / Suspension / Revocation
```

Every material transition must remain traceable.

---

# 3. Audit Objectives

The audit process must establish:

```text
Completeness

Accuracy

Integrity

Traceability

Authorization

Accountability

Reproducibility

Retention
```

---

# 4. Audit Scope

The audit scope may include:

```text
Certification Process

Certification Subject

Certification Evidence

Validation Environment

Certification Personnel

Certification Tools

Certification Registry

Security Controls

Change Management

Exception Management
```

---

# 5. Audit Independence

Audits should be sufficiently independent from the activity being audited.

For high-assurance certification, independent audit review should be used where required by policy.

---

# 6. Audit Actors

Audit activities may involve:

```text
Auditor

Certification Coordinator

Validator

Reviewer

Certification Authority

Security Auditor

Architecture Auditor
```

---

# 7. Auditor

The Auditor evaluates whether certification activities conform to applicable requirements and procedures.

Responsibilities include:

```text
Evidence Review

Audit Trail Review

Control Evaluation

Finding Creation

Finding Verification

Audit Reporting
```

---

# 8. Audit Plan

An audit plan should define:

```text
Audit ID

Audit Scope

Audit Objectives

Applicable Requirements

Audit Criteria

Evidence Sources

Audit Schedule

Auditor

Reporting Requirements
```

---

# 9. Audit Criteria

Audit criteria may be derived from:

```text
Certification Specification

Security Specification

Evidence Specification

Architecture

RFC

Protocol

Policy

Certification Level
```

---

# 10. Audit Initiation

An audit may be initiated by:

```text
Scheduled Review

Certification Renewal

Security Incident

Certification Drift

Material Change

Risk Escalation

Governance Decision
```

---

# 11. Audit Identification

Every audit must have a unique Audit ID.

Example:

```text
AUD-2026-000001
```

The identifier must remain stable for the audit lifecycle.

---

# 12. Audit Record

An audit record should contain:

```text
Audit ID

Certification ID

Subject ID

Scope

Auditor

Start Time

End Time

Status

Findings

Conclusion
```

---

# 13. Audit Lifecycle

The audit lifecycle is:

```text
PLANNED
    ↓
INITIATED
    ↓
EVIDENCE_COLLECTION
    ↓
EVALUATION
    ↓
FINDINGS
    ↓
REVIEW
    ↓
COMPLETED
```

Exception states include:

```text
SUSPENDED

CANCELLED

REOPENED
```

---

# 14. Audit Evidence

Audit evidence may include:

```text
Certification Records

Evidence Records

Validation Results

Audit Logs

Review Records

Approval Records

Change Records

Security Records
```

---

# 15. Audit Evidence Integrity

Audit evidence must retain sufficient integrity to support the audit conclusion.

Critical audit evidence should use:

```text
Hash

Digital Signature

Immutable Storage
```

where applicable.

---

# 16. Audit Trail

The audit trail records material actions affecting certification.

Examples:

```text
Request Created

Scope Approved

Requirement Changed

Validation Executed

Evidence Accepted

Finding Created

Risk Accepted

Review Completed

Decision Issued

Certification Suspended

Certification Revoked
```

---

# 17. Audit Event

An audit event should contain:

```text
Event ID

Event Type

Actor

Action

Target

Timestamp

Result

Correlation ID
```

---

# 18. Event Ordering

Audit events should preserve sufficient ordering information to reconstruct certification history.

Where timestamps alone are insufficient, the system should provide:

```text
Sequence Number

Event Version

Correlation ID
```

---

# 19. Timestamp

Audit timestamps should use a canonical time representation.

The system should record time with sufficient precision for the certification environment.

---

# 20. Actor Identity

Every privileged audit-relevant operation must identify the actor.

The actor may be:

```text
Human

Service

Automation

System
```

---

# 21. Action

Audit events must describe the performed action.

Examples:

```text
CREATE

READ

UPDATE

DELETE

APPROVE

REJECT

SUSPEND

RESUME

REVOKE

RENEW
```

---

# 22. Target

Audit events must identify the affected object.

Examples:

```text
Certification ID

Evidence ID

Finding ID

Requirement ID

Audit ID
```

---

# 23. Result

An audit event should record:

```text
SUCCESS

FAILURE

DENIED

BLOCKED
```

---

# 24. Correlation

Related events should share a correlation identifier.

Example:

```text
Certification Request
    ↓
Validation
    ↓
Evidence
    ↓
Review
```

may share one certification correlation ID.

---

# 25. Audit Integrity

Audit records must be protected from unauthorized modification.

Recommended controls include:

```text
Append-Only Storage

Hash Chains

Digital Signatures

Immutable Storage

Restricted Access
```

---

# 26. Append-Only Audit

High-assurance audit logs should be append-only.

Existing audit records must not be modified in place.

Corrections must be represented as new events.

---

# 27. Audit Hash Chain

A high-assurance implementation may chain audit records:

```text
Record N
    ↓
Hash
    ↓
Record N+1
```

This provides tamper-evident ordering.

---

# 28. Audit Signature

Critical audit records may be digitally signed.

Signatures should establish:

```text
Record Integrity

Signer Identity

Signing Time
```

---

# 29. Audit Tampering

Suspected audit tampering must trigger:

```text
Security Investigation

Integrity Verification

Certification Impact Analysis

Governance Escalation
```

---

# 30. Audit Access Control

Audit records must use least-privilege access.

Permissions should distinguish:

```text
Read

Export

Review

Administrative Control
```

---

# 31. Audit Read Access

Audit records should be readable only by authorized actors.

Sensitive audit records require additional access restrictions.

---

# 32. Audit Administrative Access

Administrative access to audit storage must be strictly controlled and itself audited.

---

# 33. Audit Export

Audit exports must preserve:

```text
Audit ID

Event IDs

Timestamps

Actor

Action

Target

Integrity References
```

---

# 34. Audit Import

Imported audit records must be verified before acceptance.

Imported records must not automatically become trusted history.

---

# 35. Audit Completeness

The audit must verify that required records exist for:

```text
All Mandatory Requirements

All Validation Activities

All Critical Findings

All Risk Decisions

All Certification Decisions
```

---

# 36. Audit Sampling

Sampling may be used when permitted by the certification level and audit policy.

Sampling methodology must be documented.

---

# 37. Full Audit

A full audit evaluates all applicable certification records.

Full audits should be used for:

```text
Critical Certification

Major Security Incident

Evidence Integrity Failure

Certification Dispute
```

when required.

---

# 38. Audit Sampling Risk

Sampling must account for the possibility that unexamined records contain additional failures.

The audit conclusion must identify sampling limitations.

---

# 39. Requirement Audit

The audit must verify:

```text
Applicable Requirements Identified

Requirement Baseline Controlled

Requirement Changes Tracked

Requirement Traceability Preserved
```

---

# 40. Scope Audit

The audit must verify:

```text
Scope Defined

Scope Approved

Scope Changes Controlled

Excluded Components Identified
```

---

# 41. Validation Audit

The audit must verify:

```text
Validation Plan Exists

Validation Was Executed

Results Were Recorded

Failures Were Preserved

Revalidation Was Controlled
```

---

# 42. Evidence Audit

The audit must verify:

```text
Evidence Exists

Evidence Is Valid

Evidence Is Traceable

Evidence Integrity Is Preserved

Evidence Status Is Correct
```

---

# 43. Finding Audit

The audit must verify:

```text
Failures Became Findings

Severity Was Assigned

Remediation Was Recorded

Closure Was Verified
```

---

# 44. Risk Audit

The audit must verify:

```text
Risks Were Identified

Risk Classification Exists

Risk Treatment Is Recorded

Risk Acceptance Is Authorized

Risk Expiration Is Controlled
```

---

# 45. Review Audit

The audit must verify:

```text
Required Reviews Occurred

Reviewers Were Authorized

Review Results Were Recorded

Review Independence Was Maintained
```

---

# 46. Decision Audit

The audit must verify:

```text
Decision Authority Was Authorized

Decision Preconditions Were Met

Decision Was Recorded

Decision Evidence Is Available
```

---

# 47. Certification Registry Audit

The audit must verify:

```text
Certification ID Is Unique

Status Is Correct

Issue Date Is Correct

Expiration Is Correct

Revocation Is Recorded

Registry Integrity Is Preserved
```

---

# 48. Security Audit

Security audit should verify:

```text
Authentication

Authorization

Evidence Integrity

Audit Integrity

Secret Handling

Dependency Security

Security Findings

Security Exceptions
```

---

# 49. Change Audit

Change audit must verify:

```text
Change Was Identified

Change Was Authorized

Impact Was Assessed

Certification Impact Was Determined

Required Revalidation Was Performed
```

---

# 50. Exception Audit

Exception audit must verify:

```text
Exception Is Documented

Risk Is Identified

Compensating Control Exists

Approval Exists

Expiration Exists
```

---

# 51. Audit Finding

An audit finding identifies a deviation from applicable criteria.

A finding should contain:

```text
Finding ID

Audit ID

Requirement

Observed Condition

Expected Condition

Evidence

Severity

Impact

Recommendation

Status
```

---

# 52. Audit Finding Severity

Audit findings may be classified:

```text
INFO

LOW

MEDIUM

HIGH

CRITICAL
```

---

# 53. Critical Audit Finding

A critical audit finding may require immediate:

```text
Escalation

Certification Impact Analysis

Suspension

Security Review
```

depending on policy.

---

# 54. Finding Root Cause

Where required, findings should identify the root cause.

Root causes may include:

```text
Process Failure

Implementation Failure

Control Failure

Configuration Failure

Human Error

Security Failure
```

---

# 55. Corrective Action

Corrective actions should define:

```text
Action

Owner

Target Date

Verification Method
```

---

# 56. Corrective Action Verification

An audit finding is not closed until corrective action has been verified.

Verification should establish:

```text
Action Completed

Control Restored

Original Failure Resolved
```

---

# 57. Audit Conclusion

An audit conclusion may be:

```text
CONFORMING

CONFORMING_WITH_FINDINGS

NON_CONFORMING

INCONCLUSIVE
```

---

# 58. Conforming

A conforming conclusion means no material nonconformity was identified within the audit scope.

---

# 59. Conforming with Findings

The certification remains within acceptable bounds, but documented findings require follow-up.

This status is permitted only when applicable policy allows it.

---

# 60. Non-Conforming

A non-conforming conclusion means one or more material requirements or controls are not satisfied.

---

# 61. Inconclusive

An audit is inconclusive when sufficient evidence is unavailable to establish a reliable conclusion.

---

# 62. Audit Report

The final audit report should contain:

```text
Audit ID

Scope

Criteria

Method

Evidence Summary

Findings

Risk

Conclusion

Recommendations

Auditor

Completion Date
```

---

# 63. Audit Report Integrity

Final audit reports should be integrity protected.

Critical reports should use:

```text
Hash

Signature

Version
```

where appropriate.

---

# 64. Audit Review

High-assurance audit reports should undergo review before finalization.

Review should verify:

```text
Evidence

Findings

Conclusion

Scope

Method
```

---

# 65. Audit Approval

Where required, the final audit report must be approved by the authorized authority.

Approval must be recorded as an audit event.

---

# 66. Audit Dispute

An audited party may dispute a finding according to applicable governance rules.

A dispute should contain:

```text
Finding

Disputed Claim

Supporting Evidence

Requested Resolution
```

---

# 67. Dispute Review

Disputes should be reviewed independently where required.

The original finding must remain visible during dispute resolution.

---

# 68. Audit Escalation

Escalation is required when:

```text
Critical Finding Exists

Audit Integrity Is Questioned

Evidence Is Conflicting

Certification Status Is Disputed

Required Authority Cannot Resolve the Issue
```

---

# 69. Audit Suspension

An audit may be suspended when:

```text
Required Evidence Is Unavailable

Security Incident Is Active

Audit Environment Is Compromised

Scope Is Unresolved
```

---

# 70. Audit Reopening

A completed audit may be reopened when:

```text
New Critical Evidence Appears

Material Audit Error Is Discovered

Evidence Integrity Is Compromised

Certification Status Changes Materially
```

---

# 71. Audit Retention

Audit records must be retained according to applicable retention policy.

Retention must support:

```text
Certification History

Re-certification

Incident Investigation

Dispute Resolution

Compliance Review
```

---

# 72. Audit Immutability

Completed audit records should be immutable.

Corrections must create new records rather than overwrite historical records.

---

# 73. Audit Disposal

Audit disposal must be:

```text
Authorized

Traceable

Auditable

Consistent With Retention Policy
```

---

# 74. Audit Backup

Critical audit records should be backed up.

Backup integrity must be periodically verified.

---

# 75. Audit Recovery

Recovery must preserve:

```text
Audit IDs

Event Ordering

Integrity References

Historical Findings

Final Conclusions
```

---

# 76. Audit Availability

Required audit records must remain available for the duration of their retention period.

---

# 77. Continuous Audit

Production certification should use continuous audit controls where practical.

Continuous audit may monitor:

```text
Certification Status

Security Events

Evidence Integrity

Configuration Drift

Dependency Changes

Critical Findings
```

---

# 78. Audit Trigger Events

Continuous audit may be triggered by:

```text
Critical Vulnerability

Material Configuration Change

Certification Drift

Evidence Integrity Failure

Critical Incident

Dependency Change
```

---

# 79. Audit Automation

Audit collection should be automated where practical.

Automation may collect:

```text
Events

Logs

Hashes

Configuration

Test Results

Registry Changes
```

Automated collection remains subject to audit validation.

---

# 80. Audit Correlation

Audit systems should correlate:

```text
Certification ID

Subject ID

Evidence ID

Validation ID

Finding ID

Risk ID

Audit ID
```

This provides end-to-end traceability.

---

# 81. Audit Traceability Matrix

A certification audit should maintain a matrix:

```text
Requirement
    ↓
Validation
    ↓
Evidence
    ↓
Finding
    ↓
Risk
    ↓
Decision
    ↓
Audit
```

Every mandatory certification requirement should be traceable through the matrix.

---

# 82. Audit Determinism

Audit conclusions should be reproducible from:

```text
Audit Criteria

Audit Scope

Audit Evidence

Audit Method

Audit Findings
```

---

# 83. Audit Reproducibility

A qualified reviewer should be able to reproduce the audit conclusion using retained records.

---

# 84. Audit Idempotency

Repeated processing of the same immutable audit event must not create conflicting audit history.

---

# 85. Audit Security

The audit system must protect against:

```text
Unauthorized Modification

Unauthorized Deletion

Identity Spoofing

Evidence Substitution

Audit Log Tampering

Unauthorized Disclosure
```

---

# 86. Audit Confidentiality

Audit information may contain sensitive material.

Access must follow:

```text
Least Privilege

Need To Know

Classification
```

---

# 87. Audit Transparency

Audit transparency requires that certification conclusions be supported by sufficient retained evidence.

Transparency does not require disclosure of restricted information.

---

# 88. Audit Accountability

Every material audit action must be attributable to an identifiable actor.

---

# 89. Audit Metrics

Certification audit systems may track:

```text
Audit Completion Rate

Finding Rate

Critical Finding Rate

Mean Remediation Time

Evidence Completeness

Audit Reopening Rate

Certification Impact Rate
```

Metrics must not replace substantive audit evaluation.

---

# 90. Audit Quality

Audit quality should be evaluated using:

```text
Evidence Sufficiency

Finding Accuracy

Traceability

Independence

Reproducibility

Timeliness
```

---

# 91. Auditor Competence

Auditors should have competence appropriate to the certification scope.

Critical certification may require expertise in:

```text
Architecture

Security

Runtime

Operations

Compliance
```

---

# 92. Audit Conflict of Interest

Conflicts of interest must be identified and managed.

An auditor with an unacceptable conflict must not perform the affected audit activity.

---

# 93. Audit Tool Security

Tools used for certification audits must be protected against:

```text
Unauthorized Modification

Configuration Tampering

Result Manipulation

Credential Abuse
```

---

# 94. Audit Environment

The audit environment should be sufficiently controlled to preserve evidence integrity.

---

# 95. Audit Configuration

Critical audit configuration should be versioned.

Examples:

```text
Audit Rules

Audit Queries

Audit Scripts

Policy Versions
```

---

# 96. Audit Tool Versioning

Audit results should identify the relevant tool version when the tool affects the conclusion.

---

# 97. Audit Script Integrity

Automated audit scripts should have integrity controls.

Examples:

```text
Source Revision

Artifact Hash

Digital Signature
```

---

# 98. Audit False Positive

False positives must be investigated rather than silently removed.

The resolution must remain traceable.

---

# 99. Audit False Negative

Potential false negatives are high-risk findings.

If discovered, the audit may require:

```text
Re-evaluation

Expanded Sampling

Full Audit

Certification Impact Analysis
```

---

# 100. Audit Scope Expansion

The audit scope may be expanded when evidence indicates material risk outside the original scope.

Scope expansion must be documented and approved.

---

# 101. Audit Scope Reduction

Scope reduction requires explicit justification.

It must not be used to avoid known findings.

---

# 102. Audit Evidence Conflict

Conflicting evidence must be preserved and investigated.

The auditor must document the basis for the final conclusion.

---

# 103. Audit Evidence Freshness

Auditors must determine whether evidence remains sufficiently current for the audit objective.

---

# 104. Audit Evidence Reuse

Historical evidence may be reused only when:

```text
Subject Matches

Version Matches

Scope Matches

Integrity Is Valid

Evidence Remains Applicable
```

---

# 105. Audit and Certification Renewal

Renewal audits should verify:

```text
Current Requirements

Current Security State

Historical Findings

Current Evidence

Current Configuration

Current Dependencies
```

---

# 106. Audit and Suspension

Suspension-related audits should determine:

```text
Trigger

Impact

Risk

Affected Requirements

Required Remediation

Resume Conditions
```

---

# 107. Audit and Revocation

Revocation-related audits should preserve:

```text
Revocation Trigger

Supporting Evidence

Authority Decision

Certification Status History
```

---

# 108. Audit and Incidents

Security incidents affecting certified subjects must be included in the audit history when relevant.

---

# 109. Audit Events

The audit subsystem should emit typed events:

```text
AuditCreated

AuditStarted

AuditEvidenceCollected

AuditFindingCreated

AuditFindingUpdated

AuditFindingClosed

AuditReviewed

AuditApproved

AuditCompleted

AuditSuspended

AuditReopened
```

---

# 110. Audit Process Contract

The audit process contract requires:

```text
Explicit Scope

Explicit Criteria

Explicit Evidence

Explicit Findings

Explicit Conclusion

Explicit Auditor Identity

Explicit Audit Trail
```

---

# 111. Audit Conformance

An implementation conforms to this specification when it supports:

```text
Audit Planning

Audit Execution

Audit Evidence

Audit Trail

Audit Findings

Audit Review

Audit Conclusion

Audit Retention

Audit Integrity
```

---

# 112. Certification Level Audit Requirements

Audit assurance increases with certification level.

```text
Level 1
Basic Audit Trail

Level 2
Formal Certification Audit

Level 3
Production Assurance Audit

Level 4
Critical Independent Audit
```

---

# 113. Level 1 Audit

Level 1 should establish:

```text
Traceability

Basic Audit Records

Basic Evidence Review
```

---

# 114. Level 2 Audit

Level 2 should additionally establish:

```text
Formal Audit Plan

Requirement Audit

Validation Audit

Finding Review

Decision Audit
```

---

# 115. Level 3 Audit

Level 3 should additionally establish:

```text
Operational Audit

Security Audit

Change Audit

Continuous Monitoring

Recovery Audit
```

---

# 116. Level 4 Audit

Level 4 should additionally establish:

```text
Independent Audit

Enhanced Evidence Verification

Strong Audit Integrity

Continuous Assurance

Formal Security Audit

Enhanced Governance Review
```

---

# 117. Audit Failure Gate

Certification audit must block or escalate when:

```text
Critical Audit Finding Exists

Audit Evidence Is Insufficient

Audit Trail Is Incomplete

Audit Integrity Is Unverifiable

Required Independent Review Is Missing
```

---

# 118. Audit Report Finalization

An audit is finalized only when:

```text
Scope Is Confirmed

Evidence Is Reviewed

Findings Are Recorded

Conclusion Is Approved

Audit Record Is Integrity Protected
```

---

# 119. Final Audit Model

The SH-3 certification audit model is:

```text
PLAN
    ↓
COLLECT
    ↓
VERIFY
    ↓
EVALUATE
    ↓
FIND
    ↓
REVIEW
    ↓
CONCLUDE
    ↓
RETAIN
    ↓
MONITOR
```

---

# 120. Final Definition

SH-3 Certification Audit is the controlled mechanism for independently or systematically verifying that certification activities and results remain compliant, traceable, authorized, and trustworthy.

A valid audit must establish:

```text
What Was Evaluated

+

Against Which Criteria

+

Using Which Evidence

+

By Which Actor

+

With Which Findings

+

Under Which Decision

+

With Which Historical Record
```

The audit therefore provides the accountability layer of SH-3 certification and preserves the evidence necessary to verify the integrity of certification decisions throughout their lifecycle.

---

# End of Document
