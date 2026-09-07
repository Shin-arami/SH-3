# SH-3 Certification Evidence Specification

Version:
1.0.0

Status:
Architecture Specification

Category:
Certification Evidence

---

# 1. Purpose

This document defines the evidence model used by SH-3 certification.

Certification evidence provides the verifiable basis for determining whether an SH-3 subject satisfies applicable certification requirements.

The evidence model establishes:

- Evidence types
- Evidence identity
- Evidence ownership
- Evidence collection
- Evidence validation
- Evidence integrity
- Evidence traceability
- Evidence sufficiency
- Evidence retention
- Evidence lifecycle
- Evidence protection

---

# 2. Evidence Principle

Certification must be evidence-based.

The fundamental relationship is:

```text
Requirement
    ↓
Validation Rule
    ↓
Evidence
    ↓
Finding
    ↓
Certification Decision
```

No mandatory certification requirement may be considered satisfied without sufficient evidence.

---

# 3. Evidence Definition

Evidence is a verifiable artifact that supports a certification evaluation.

Evidence may demonstrate:

```text
Implementation

Behavior

Configuration

Security

Operation

Testing

Compliance

Integrity

Governance
```

---

# 4. Evidence Subject

Every evidence artifact must identify the subject to which it applies.

The subject should include:

```text
Subject ID

Subject Version

Subject Type

Certification ID
```

---

# 5. Evidence Identity

Every significant evidence artifact must have a unique Evidence ID.

Example:

```text
EVD-000001
EVD-000002
EVD-000003
```

The identifier must remain stable for the lifetime of the evidence record.

---

# 6. Evidence Record

An evidence record should contain:

```text
Evidence ID

Evidence Type

Subject ID

Subject Version

Source

Collector

Timestamp

Integrity Reference

Requirement References

Validation References

Status
```

---

# 7. Evidence Types

SH-3 evidence may include:

```text
Source Evidence

Build Evidence

Test Evidence

Static Analysis Evidence

Runtime Evidence

Configuration Evidence

Security Evidence

Operational Evidence

Deployment Evidence

Review Evidence

Audit Evidence

Integrity Evidence
```

---

# 8. Source Evidence

Source evidence demonstrates the implementation being evaluated.

Examples:

```text
Source File

Commit

Tag

Release Artifact

Repository Snapshot
```

Source evidence should identify the exact version evaluated.

---

# 9. Build Evidence

Build evidence demonstrates how the evaluated artifact was produced.

Examples:

```text
Build Record

Build Configuration

Compiler Information

Package Manifest

Dependency Lock

Build Artifact Hash
```

---

# 10. Test Evidence

Test evidence demonstrates execution of defined tests.

Examples:

```text
Unit Test Result

Integration Test Result

System Test Result

Regression Test Result

Failure Test Result
```

Test evidence should include the executed test version.

---

# 11. Static Analysis Evidence

Static analysis evidence may include:

```text
Type Checking

Linting

Dependency Analysis

Security Scanning

Architecture Analysis

Schema Analysis
```

The analysis tool and version should be recorded where relevant.

---

# 12. Runtime Evidence

Runtime evidence demonstrates behavior during execution.

Examples:

```text
Logs

Metrics

Traces

Health Results

Runtime Events

Execution Results
```

Runtime evidence must identify the relevant execution environment.

---

# 13. Configuration Evidence

Configuration evidence demonstrates the configuration used during evaluation.

Examples:

```text
Configuration File

Environment Definition

Profile

Feature Configuration

Policy Configuration
```

Critical configuration should include an integrity reference.

---

# 14. Security Evidence

Security evidence demonstrates applicable security controls.

Examples:

```text
Security Test

Threat Model

Access Control Test

Authentication Test

Authorization Test

Secrets Validation

Dependency Security Report
```

Sensitive security evidence must be protected according to security policy.

---

# 15. Operational Evidence

Operational evidence demonstrates production behavior.

Examples:

```text
Health Check

Startup Test

Shutdown Test

Recovery Test

Capacity Test

Monitoring Result
```

---

# 16. Deployment Evidence

Deployment evidence demonstrates that the certified deployment can be reproduced and operated within its defined scope.

Examples:

```text
Deployment Manifest

Environment Definition

Artifact Reference

Configuration Reference

Deployment Result

Rollback Result
```

---

# 17. Review Evidence

Review evidence demonstrates that required human or automated reviews were completed.

Examples:

```text
Architecture Review

Security Review

Code Review

Governance Review

Certification Review
```

---

# 18. Audit Evidence

Audit evidence demonstrates process integrity and historical traceability.

Examples:

```text
Audit Record

State Transition

Approval Record

Decision Record

Exception Record
```

---

# 19. Integrity Evidence

Integrity evidence demonstrates that an artifact has not been modified unexpectedly.

Examples:

```text
Cryptographic Hash

Digital Signature

Immutable Reference

Version Identifier
```

---

# 20. Evidence Source

Every evidence record should identify its source.

Sources may include:

```text
Repository

Build System

Test System

Runtime

Deployment System

Monitoring System

Reviewer

Certification System
```

---

# 21. Evidence Collector

The collector is the actor or system that produced or registered the evidence.

The collector may be:

```text
Human

Automated Tool

CI System

Runtime System

Certification System
```

---

# 22. Evidence Timestamp

Evidence must record when it was produced or captured.

At minimum:

```text
Collected At
```

should be recorded.

Critical evidence may additionally require:

```text
Started At

Completed At

Verified At
```

---

# 23. Evidence Version

Evidence must be versioned when the underlying artifact or procedure is version-sensitive.

Examples:

```text
Test Suite Version

Tool Version

Configuration Version

Policy Version

Environment Version
```

---

# 24. Evidence Integrity

Evidence integrity must be verifiable.

The preferred integrity model is:

```text
Evidence Artifact
    ↓
Hash
    ↓
Evidence Record
    ↓
Certification Record
```

---

# 25. Cryptographic Hash

Critical evidence should have a cryptographic hash.

The hash identifies the exact evidence artifact.

Example:

```text
SHA-256:<digest>
```

The exact algorithm may be defined by the applicable security policy.

---

# 26. Digital Signature

Digital signatures may be used for high-assurance evidence.

A signature should establish:

```text
Artifact Integrity

Signer Identity

Signing Time
```

---

# 27. Evidence Immutability

Evidence used for a final certification decision should be immutable or otherwise protected against unauthorized modification.

If evidence must be replaced, the original record must remain available in the audit history.

---

# 28. Evidence Chain of Custody

Critical evidence should maintain a chain of custody.

The chain may contain:

```text
Created By

Collected At

Transferred By

Stored At

Verified By

Used By
```

---

# 29. Evidence Traceability

Evidence must be traceable to one or more certification requirements.

The relationship is:

```text
Requirement
    ↓
Validation
    ↓
Evidence
```

Evidence without a defined purpose should not be used as mandatory certification evidence.

---

# 30. Bidirectional Traceability

Where practical, traceability must work in both directions.

From requirement:

```text
Requirement
    ↓
Validation
    ↓
Evidence
```

From evidence:

```text
Evidence
    ↓
Validation
    ↓
Requirement
```

---

# 31. Evidence to Finding Traceability

Evidence must be traceable to findings.

```text
Evidence
    ↓
Finding
    ↓
Decision
```

A finding must identify the evidence supporting its conclusion.

---

# 32. Evidence to Certification Traceability

Evidence must ultimately be traceable to the certification record.

```text
Evidence
    ↓
Finding
    ↓
Certification Decision
    ↓
Certification ID
```

---

# 33. Evidence Sufficiency

Evidence is sufficient when it provides enough verifiable information to support the relevant certification conclusion.

Sufficiency depends on:

```text
Requirement

Certification Level

Validation Method

Risk

Evidence Quality
```

---

# 34. Evidence Quality

Evidence quality may be evaluated using:

```text
Accuracy

Completeness

Relevance

Freshness

Integrity

Traceability

Reproducibility
```

---

# 35. Evidence Accuracy

Evidence must accurately represent the evaluated state.

Evidence must not be altered to produce a desired certification result.

---

# 36. Evidence Completeness

Evidence is complete when all information required by the applicable validation rule is present.

Incomplete evidence must not be treated as passing evidence.

---

# 37. Evidence Relevance

Evidence must directly support the requirement being evaluated.

Unrelated evidence must not be used to compensate for missing mandatory evidence.

---

# 38. Evidence Freshness

Evidence must be sufficiently current for the certification scope.

Freshness depends on:

```text
Certification Level

Requirement

Subject Stability

Security Risk

Operational Risk
```

---

# 39. Evidence Reproducibility

Where practical, evidence should permit an authorized party to reproduce the relevant validation.

Reproducibility may require:

```text
Input

Environment

Configuration

Dependency Versions

Tool Versions

Procedure
```

---

# 40. Evidence Validity

Evidence validity depends on:

```text
Subject Match

Version Match

Scope Match

Environment Match

Requirement Match

Integrity
```

Evidence failing any mandatory validity condition must be rejected or reviewed.

---

# 41. Subject Match

Evidence must correspond to the exact certified subject.

Evidence from a different subject must not be silently reused.

---

# 42. Version Match

Evidence must correspond to the evaluated subject version.

Example:

```text
Subject:
SH3 Runtime v2.0

Evidence:
SH3 Runtime v1.9
```

is not automatically valid for v2.0.

---

# 43. Scope Match

Evidence must apply to the certification scope.

Evidence outside the scope may be informational but must not automatically satisfy scoped requirements.

---

# 44. Environment Match

Environment-dependent evidence must identify the environment.

Examples:

```text
Development

Test

Staging

Production
```

Evidence from one environment must not automatically certify another environment.

---

# 45. Requirement Match

Evidence must support the exact requirement or a formally mapped requirement.

Indirect evidence may be accepted only when the certification policy permits it.

---

# 46. Evidence Collection

Evidence collection should follow an approved plan.

The process is:

```text
Identify Requirement

↓

Identify Evidence

↓

Collect Evidence

↓

Verify Evidence

↓

Register Evidence

↓

Link Evidence
```

---

# 47. Evidence Registration

Evidence should be registered before it is used in the final certification decision.

Registration establishes:

```text
Identity

Metadata

Integrity

Traceability
```

---

# 48. Evidence Verification

Evidence verification checks:

```text
Artifact Exists

Artifact Is Readable

Artifact Is Relevant

Artifact Is Complete

Integrity Is Valid

Subject Is Correct

Version Is Correct
```

---

# 49. Evidence Acceptance

Evidence may be marked:

```text
ACCEPTED

REJECTED

PENDING_REVIEW

EXPIRED
```

Only accepted evidence may satisfy a mandatory requirement.

---

# 50. Evidence Rejection

Evidence may be rejected because of:

```text
Integrity Failure

Wrong Version

Wrong Subject

Wrong Environment

Insufficient Content

Missing Traceability

Expired Evidence

Unauthorized Source
```

---

# 51. Evidence Expiration

Evidence may expire because:

```text
Subject Changed

Requirement Changed

Environment Changed

Security State Changed

Validity Period Ended
```

Expired evidence must not be treated as current evidence.

---

# 52. Evidence Refresh

Evidence refresh replaces stale evidence with newly validated evidence.

The previous evidence record must remain available for historical traceability.

---

# 53. Evidence Supersession

When new evidence replaces old evidence:

```text
Old Evidence
    ↓
Superseded By
    ↓
New Evidence
```

The relationship must be recorded.

---

# 54. Evidence Retention

Evidence retention must support:

```text
Certification Audit

Re-certification

Incident Investigation

Dispute Resolution

Compliance Review
```

Retention periods are defined by applicable policy.

---

# 55. Evidence Storage

Evidence storage should provide:

```text
Integrity

Availability

Access Control

Versioning

Auditability
```

Critical evidence should use protected storage.

---

# 56. Evidence Access Control

Evidence access must follow least privilege.

Access may be controlled by:

```text
Role

Certification

Subject

Evidence Sensitivity

Security Classification
```

---

# 57. Sensitive Evidence

Sensitive evidence may include:

```text
Secrets

Security Findings

Vulnerability Details

Personal Data

Internal Architecture

Restricted Operational Data
```

Sensitive evidence must not be unnecessarily exposed.

---

# 58. Evidence Redaction

Evidence may be redacted for publication while preserving the original evidence internally.

The relationship must be:

```text
Original Evidence
    ↓
Redacted Representation
```

The redacted representation must not replace the original evidence record.

---

# 59. Evidence Confidentiality

Confidential evidence must be protected from unauthorized disclosure.

Certification publication must expose only authorized information.

---

# 60. Evidence Availability

Evidence required for an active certification must remain retrievable according to retention policy.

Loss of critical evidence may trigger certification impact analysis.

---

# 61. Evidence Backup

Critical evidence should be backed up according to operational policy.

Backup integrity should be periodically verified.

---

# 62. Evidence Recovery

Evidence recovery procedures must preserve:

```text
Evidence ID

Integrity Reference

Original Timestamp

Traceability

Audit History
```

---

# 63. Evidence Duplication

Identical evidence may be referenced by multiple requirements when permitted.

The evidence record should remain singular while multiple traceability links are maintained.

---

# 64. Evidence Reuse

Evidence reuse is permitted only when:

```text
Subject Matches

Version Matches

Scope Matches

Environment Matches

Evidence Remains Valid
```

---

# 65. Evidence Reuse Restrictions

Evidence must not be reused merely because:

```text
It Looks Similar

It Came From The Same Project

It Passed Previously

It Was Produced Recently
```

Formal applicability must be established.

---

# 66. Evidence Aggregation

Multiple evidence artifacts may collectively support one requirement.

Example:

```text
Test Result
+
Configuration
+
Runtime Log
=
Requirement Evidence
```

All constituent artifacts must remain traceable.

---

# 67. Evidence Sufficiency for Aggregation

Aggregated evidence is sufficient only when the complete set establishes the required conclusion.

Missing constituent evidence must remain visible.

---

# 68. Evidence Conflict

When evidence conflicts:

```text
Evidence A → PASS

Evidence B → FAIL
```

the conflict must be investigated.

The certification process must not select the favorable evidence without justification.

---

# 69. Evidence Conflict Resolution

Conflict resolution may require:

```text
Additional Validation

Evidence Verification

Environment Verification

Reviewer Analysis
```

The final conclusion must document the resolution.

---

# 70. Evidence Failure

Evidence processing failures include:

```text
EvidenceCollectionFailure

EvidenceIntegrityFailure

EvidenceValidationFailure

EvidenceStorageFailure

EvidenceTraceabilityFailure

EvidenceAccessFailure
```

---

# 71. Evidence Failure Handling

Evidence failures must:

```text
Preserve Existing Evidence

Record Failure

Prevent Invalid Acceptance

Generate Audit Event
```

---

# 72. Evidence Tampering

Suspected evidence tampering must trigger:

```text
Evidence Integrity Review

Security Investigation

Certification Impact Analysis
```

Critical tampering may require immediate certification suspension.

---

# 73. Evidence Forgery

Confirmed fabricated evidence is a critical certification integrity violation.

The certification must be reviewed immediately.

Possible actions include:

```text
Suspension

Revocation

Investigation

Audit Escalation
```

---

# 74. Evidence Chain Model

The complete evidence chain is:

```text
Requirement
    ↓
Validation Rule
    ↓
Validation Execution
    ↓
Evidence
    ↓
Finding
    ↓
Risk
    ↓
Certification Decision
```

Breaking this chain without documented justification invalidates traceability.

---

# 75. Evidence and Certification Level

Evidence requirements increase with certification level.

```text
Level 0
Initial Development Evidence

Level 1
Conformance Evidence

Level 2
Verification Evidence

Level 3
Production Evidence

Level 4
Critical Assurance Evidence
```

---

# 76. Level 1 Evidence

Level 1 should demonstrate:

```text
Architecture

Interfaces

Types

Schemas

Basic Behavior
```

---

# 77. Level 2 Evidence

Level 2 additionally requires evidence for:

```text
Behavior

Integration

Failure Handling

Determinism

Compatibility
```

---

# 78. Level 3 Evidence

Level 3 additionally requires:

```text
Security

Operations

Performance

Recovery

Rollback

Deployment

Observability
```

---

# 79. Level 4 Evidence

Level 4 additionally requires:

```text
Formal Security Review

Formal Architecture Review

Integrity Assurance

Failure Isolation

Incident Response

Continuous Monitoring

Enhanced Governance
```

---

# 80. Evidence and Certification Decision

The Certification Authority must be able to determine:

```text
Which Requirement

Was Validated

Using Which Evidence

With Which Result

Under Which Conditions
```

---

# 81. Evidence Index

A certification package should contain an evidence index.

Example:

```text
Evidence ID | Requirement | Type | Status
EVD-0001    | REQ-001     | Test | ACCEPTED
EVD-0002    | REQ-002     | Hash | ACCEPTED
EVD-0003    | REQ-003     | Review | ACCEPTED
```

---

# 82. Evidence Matrix

The evidence matrix provides complete traceability.

```text
Requirement | Validation | Evidence | Finding | Result
```

Example:

```text
REQ-001 | VAL-001 | EVD-001 | FIND-001 | PASS
REQ-002 | VAL-002 | EVD-002 | FIND-002 | PASS
REQ-003 | VAL-003 | EVD-003 | FIND-003 | FAIL
```

---

# 83. Evidence Metadata

Minimum metadata should include:

```text
Evidence ID

Type

Source

Subject

Version

Timestamp

Integrity

Requirement References

Status
```

---

# 84. Evidence Schema

A conceptual evidence record is:

```text
Evidence {
    id
    type
    subject_id
    subject_version
    source
    collector
    created_at
    verified_at
    integrity
    requirement_refs
    validation_refs
    status
}
```

Concrete implementations must use strongly typed structures.

---

# 85. Evidence Events

The evidence subsystem should emit typed events:

```text
EvidenceCreated

EvidenceRegistered

EvidenceVerified

EvidenceAccepted

EvidenceRejected

EvidenceSuperseded

EvidenceExpired

EvidenceRestored

EvidenceIntegrityFailed
```

---

# 86. Evidence Determinism

Evidence registration must be deterministic for identical:

```text
Artifact

Metadata

Integrity Reference
```

Duplicate registration must not create ambiguous identity.

---

# 87. Evidence Idempotency

Registering the same immutable evidence multiple times should produce an idempotent result when the evidence identity is unchanged.

---

# 88. Evidence Security

The evidence subsystem must protect against:

```text
Unauthorized Modification

Unauthorized Deletion

Evidence Substitution

Identity Spoofing

Access Bypass

Audit Tampering
```

---

# 89. Evidence Deletion

Evidence required for active or historical certification must not be deleted outside the retention and governance policy.

Deletion must be auditable.

---

# 90. Evidence Disposal

When retention expires, disposal must:

```text
Be Authorized

Be Auditable

Protect Sensitive Information

Preserve Required Metadata
```

---

# 91. Evidence Audit

Evidence audit must be able to answer:

```text
Who Created It?

When Was It Created?

What Subject Did It Represent?

Who Verified It?

Which Requirement Did It Support?

Was It Modified?

Was It Superseded?

Was It Used In A Certification Decision?
```

---

# 92. Evidence Governance

Evidence governance must define:

```text
Ownership

Retention

Access

Classification

Integrity

Review

Disposal
```

---

# 93. Evidence Ownership

Every critical evidence set should have an owner responsible for:

```text
Accuracy

Availability

Integrity

Retention
```

---

# 94. Evidence Review

Critical evidence should undergo formal review.

Review may verify:

```text
Correct Subject

Correct Version

Correct Scope

Correct Method

Sufficient Quality
```

---

# 95. Evidence Approval

Where required, evidence approval must be explicit.

Approval must not modify the evidence itself.

---

# 96. Evidence Independence

Evidence generated by the applicant may be acceptable, but independent verification should be used where required by certification level or risk.

---

# 97. Evidence Automation

Evidence collection should be automated where practical.

Automation reduces:

```text
Manual Error

Evidence Omission

Inconsistent Collection

Traceability Loss
```

Automated evidence remains subject to validation.

---

# 98. Evidence Pipeline

The preferred evidence pipeline is:

```text
Collect
    ↓
Normalize
    ↓
Hash
    ↓
Register
    ↓
Validate
    ↓
Link
    ↓
Review
    ↓
Retain
```

---

# 99. Evidence Normalization

Evidence metadata should use standardized representations.

Examples:

```text
Canonical IDs

Canonical Timestamps

Canonical Versions

Canonical Hash Format
```

---

# 100. Evidence Interoperability

Evidence should be exchangeable between certification tools without losing:

```text
Identity

Integrity

Traceability

Timestamp

Source

Status
```

---

# 101. Evidence Export

Evidence export should preserve:

```text
Evidence ID

Metadata

Integrity Reference

Requirement Links

Validation Links

Audit References
```

---

# 102. Evidence Import

Imported evidence must undergo validation before acceptance.

Imported evidence must not automatically become trusted evidence.

---

# 103. Evidence Portability

Evidence may be portable between certification processes only when its applicability and integrity remain valid.

---

# 104. Evidence Certification Package

A certification package should contain:

```text
Evidence Index

Evidence Artifacts

Integrity References

Requirement Matrix

Validation Matrix

Finding Matrix

Audit References
```

---

# 105. Evidence Package Integrity

The complete evidence package should have an integrity mechanism.

Examples:

```text
Package Hash

Manifest

Digital Signature
```

---

# 106. Evidence Manifest

A manifest may contain:

```text
Evidence ID

Artifact Name

Artifact Hash

Artifact Version

Artifact Type
```

---

# 107. Evidence Package Verification

Before final certification review:

```text
All Required Evidence Exists

All Hashes Match

All References Resolve

All Required Evidence Is Accepted
```

must be verified.

---

# 108. Evidence Completeness Gate

The certification process must block final decision when mandatory evidence is missing.

---

# 109. Evidence Integrity Gate

The certification process must block final decision when critical evidence integrity cannot be established.

---

# 110. Evidence Traceability Gate

The certification process must block final decision when mandatory evidence cannot be traced to its requirement.

---

# 111. Evidence Freshness Gate

The certification process must block final decision when required evidence has expired and no valid replacement exists.

---

# 112. Evidence Retention Gate

Certification records must not be issued when the required evidence cannot be retained according to applicable policy.

---

# 113. Evidence and Continuous Assurance

For Level 3 and Level 4 certifications, selected evidence may be continuously refreshed.

Examples:

```text
Security State

Dependency State

Runtime Health

Configuration State

Integrity State
```

---

# 114. Continuous Evidence

Continuous evidence may be used to detect certification drift.

When continuous evidence indicates a violation:

```text
Detection

↓

Impact Analysis

↓

Certification Decision
```

must be initiated according to policy.

---

# 115. Evidence and Incident Response

Security or operational incidents may generate certification evidence.

Incident evidence should be linked to:

```text
Incident ID

Subject

Certification ID

Affected Requirement
```

---

# 116. Evidence and Change Management

Change evidence should establish:

```text
What Changed

Who Changed It

When It Changed

Why It Changed

Which Certification Is Affected
```

---

# 117. Evidence and Re-certification

Historical evidence may support re-certification but current requirements must be evaluated according to the current certification policy.

---

# 118. Evidence and Revocation

Evidence supporting revocation must be preserved as part of the certification audit record.

---

# 119. Evidence and Suspension

Evidence supporting suspension must identify:

```text
Trigger

Affected Requirement

Observed Condition

Risk

Decision
```

---

# 120. Evidence Conformance

An implementation conforms to this specification when it supports:

```text
Evidence Identity

Evidence Registration

Evidence Integrity

Evidence Validation

Evidence Traceability

Evidence Acceptance

Evidence Rejection

Evidence Retention

Evidence Audit
```

---

# 121. Anti-Patterns

The following are prohibited:

- Certification without evidence
- Evidence without an identifiable subject
- Evidence without version information where version matters
- Evidence without requirement traceability
- Reusing expired evidence as current evidence
- Replacing evidence without preserving history
- Selecting favorable evidence while ignoring conflicting evidence
- Modifying evidence after certification without audit
- Treating applicant claims as sufficient evidence by default
- Using test count as proof of certification
- Using unrelated evidence to compensate for mandatory evidence
- Deleting certification evidence without authorization
- Publishing sensitive evidence without authorization

---

# 122. Final Evidence Model

The SH-3 evidence model is:

```text
Artifact

+

Identity

+

Source

+

Timestamp

+

Integrity

+

Validation

+

Requirement Traceability

+

Finding Traceability

+

Certification Traceability
```

---

# 123. Final Definition

SH-3 certification evidence is the controlled, verifiable, traceable, and integrity-protected basis on which certification findings and decisions are established.

Evidence must identify the exact subject and applicable version, remain within the certification scope, preserve integrity, maintain traceability, and remain sufficiently current for the certification decision.

Certification evidence is therefore not merely collected data.

It is a governed assurance artifact connecting:

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

Certification Decision
```

---

# End of Document
