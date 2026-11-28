# P3-2G G-D — Persistent Replay Integrity Trust Boundary

- **Status:** Design gate / implementation not started
- **Finding:** G-04
- **Severity:** P1
- **Target branch:** `v2.2-development`
- **Audit baseline:** `03938815b608f6499f797f2b9ed3ae1c14a614ae`
- **Current verified implementation baseline:** `53ed58bb813066b9b3b1bbff80dd6329c90d2336`

## 1. Purpose

Define exactly what SH-3 persistent replay integrity values prove, which adversaries are in scope, and whether a database writer must be prevented from silently rewriting both a record and its digest.

This document is a design and acceptance plan. It does not add code, change the database schema, rotate keys, or authorize a production operation.

## 2. Verified current implementation

The current implementation uses unkeyed SHA-256 digests over canonical data. The digest is stored alongside the protected record in the same SQLite database. An actor with sufficient write access to the database can alter a record and recompute the digest. Therefore these values provide consistency/corruption detection, not authenticity against a malicious database writer.

The reviewed digest surfaces include:

- `infrastructure/security/evidence.py`: `EvidenceRecord` canonical payload digest and `verify()`.
- `infrastructure/security/persistent_store.py`: replay Stage input fingerprints and persisted Stage result integrity.
- `infrastructure/security/persistent_operation_store.py`: operation input fingerprints, Action/Rollback result integrity, and Action Plan integrity.

Do not describe these SHA-256 values as signatures, authenticated evidence, or tamper-proof storage.

## 3. Threat-model decision gate

Choose one policy before implementing G-D.

### Option A — Bounded local-storage threat model

Accept the existing SHA-256 mechanism only for accidental corruption and isolated/uncoordinated modification detection. Explicitly exclude an actor who can rewrite the SQLite database and recompute its hashes from the authenticity threat model.

Required compensating controls:

- Restrict database and backup write access using least-privilege OS ACLs.
- Keep production database files outside the source checkout.
- Protect backups and audit exports in a separate access boundary.
- Document that a privileged database writer can forge the current digest fields.
- Do not claim authenticity against a database writer.

This option minimizes code and key-management complexity but does not meet a threat model that includes malicious database writers.

### Option B — Authenticated persistent records (recommended when database-writer tampering is in scope)

Add HMAC-SHA-256 authentication using key material held outside SQLite and outside the repository. Use a key-provider abstraction so local tests, deployment secret stores, and future KMS integrations are replaceable.

Required design properties:

- Use Python's standard-library `hmac` and `hashlib` unless a separately justified asymmetric-signature requirement emerges.
- Use `hmac.compare_digest()` for tag comparison.
- Authenticate canonical bytes with explicit domain separation, record kind, format version, stable record identity, and relevant tenant/cycle/parent identity. Prevent digest/tag reuse across evidence, Stage, Action, Rollback, and Action Plan domains.
- Store only an algorithm/version identifier, key ID, and authentication tag with the record. Never store key material in SQLite, snapshots, source control, logs, or ordinary diagnostics.
- Inject a typed key-provider protocol. The provider must support signing with the active key and verification using retained historical key IDs.
- Missing provider, unknown key ID, malformed tag, or verification failure must fail closed in authenticated mode.
- Keep key provisioning, rotation, revocation, backup/restore access, and emergency recovery outside the database trust boundary.

This option adds security and operational complexity and must not be implemented until the deployment's key custody and restore requirements are concrete.

## 4. Compatibility and historical data policy

- Existing `sha256:` rows are legacy unkeyed records. They must never be silently relabeled as HMAC-authenticated.
- An authenticated deployment must have an explicit policy for legacy rows: reject them, allow them only in a separately identified legacy-read mode, or require a reviewed offline attestation/re-sealing procedure.
- Re-sealing a legacy record with HMAC does not prove that the record was historically authentic. It proves only that the record was accepted and signed at the time of re-sealing.
- Do not use an automatic startup migration to upgrade trust labels.
- If the chosen format changes persisted columns or schema metadata, add a new explicit schema migration, backup/restore contract, rollback tests, and a compatibility window. Do not repurpose G-C's schema version 1 in place.
- Key rotation must preserve the ability to verify records signed by retained prior keys until the retention policy permits retirement.

## 5. Data and trust boundary inventory

Before implementation, produce a mapping from each persisted field to its integrity/authenticity policy:

| Data | Current mechanism | G-D requirement |
|---|---|---|
| Evidence record | Canonical SHA-256 in `EvidenceRecord.integrity` | Authenticate full semantic record and identity if Option B |
| Replay Stage result | Canonical SHA-256 result digest | Authenticate result and owning stage/cycle identity if Option B |
| Replay operation result | Canonical SHA-256 result digest | Authenticate operation identity, kind, parent, tenant scope, and result if Option B |
| Action Plan | Canonical SHA-256 JSON digest | Authenticate ordered Action contract descriptors and plan identity if Option B |
| Replay input fingerprints | SHA-256 fingerprints | Decide whether these remain deterministic identity fingerprints or require authentication as part of a signed parent record |
| Claim/lease/ownership state | Structural checks, transaction and generation fencing | Decide whether the authenticity guarantee includes mutable claim lifecycle fields |

Do not implement only `EvidenceRecord` HMAC while continuing to describe the entire replay ledger as authenticated. Scope every claim to the exact protected data.

## 6. Proposed implementation boundaries for Option B

If Option B is selected, prepare a separate implementation PR with the following layers:

1. `infrastructure/security/integrity.py`: typed protocol and immutable authentication metadata; standard-library HMAC implementation.
2. Key-provider boundary: active signing key and lookup by key ID; no concrete secret-manager dependency until deployment target is selected.
3. Canonicalization: versioned, domain-separated serialization shared by Evidence, Stage, Operation, and Action Plan records.
4. Persistence adapters: explicit integrity-policy injection; no hidden global key state.
5. Readiness: report authentication mode and fail closed according to externally configured policy. A database-controlled flag alone must not be able to downgrade authenticated mode.
6. Backup/restore: preserve tags and require the matching verification keyring at restore/readiness time.
7. Migration: preserve legacy SHA-256 tags and mark them as legacy; no implicit re-signing or authenticity upgrade.
8. Operations: define secret provisioning, least privilege, key rotation, recovery, and loss-of-key behavior.

Keep dependencies flowing downward in the SH-3 architecture. Do not add key-management dependencies to Foundation or make infrastructure import deployment-specific providers.

## 7. Required tests

For Option B, tests must cover at least:

- Correct HMAC verifies after process restart.
- A stored payload altered without updating its tag is rejected.
- A database writer that changes both payload and an unkeyed SHA-256 digest cannot forge a valid HMAC.
- Wrong key, unknown key ID, missing key, malformed tag, and revoked key fail according to the documented policy.
- `compare_digest` is used for tag comparison.
- Cross-domain substitution (Evidence vs Stage vs Operation vs Plan) is rejected.
- Cross-tenant, cross-cycle, and parent-identity substitution is rejected.
- Rotation: records signed with the prior retained key still verify, while new writes use the active key.
- Backup/restore preserves authenticated records and fails closed when the needed verification key is unavailable.
- G-C schema migration preserves legacy tags exactly and does not mark legacy rows authenticated.
- Readiness and Runtime policy cannot be downgraded by editing a metadata value stored only in SQLite.
- Concurrency and partial-write failure leave no accepted record with a missing or mismatched tag.

For Option A, tests and documentation must instead demonstrate the declared bounded threat model and verify filesystem/access-control assumptions at the deployment layer where possible.

## 8. Exit criteria

G-D is complete only when:

- The responsible owner records the selected threat model and accepted attacker capabilities.
- Every persisted integrity field is inventoried and has an explicit assurance level.
- The selected option's code and operational requirements are implemented and reviewed.
- Legacy record semantics and key rotation/recovery behavior are documented.
- Tampering tests prove the exact stated guarantee; no broader claim is made.
- Ruff, Mypy, focused tests, full pytest, and backup/restore compatibility checks pass.
- Any required schema migration is explicit, backed up, transactional, and separately approved.

## 9. Recommended next action

Record the threat-model decision first. For a production environment where an actor with SQLite write access is in scope, choose **Option B** and design external key custody before implementing the HMAC provider. Otherwise choose **Option A** and formally limit the integrity guarantee to corruption/partial-tamper detection.

No production database migration, data re-signing, or key rotation is authorized by this plan.
