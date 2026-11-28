# P3-2G G-D — Persistent Replay Integrity Trust Boundary

- **Status:** Design gate / implementation not started
- **Finding:** G-04
- **Severity:** P1
- **Target branch:** `v2.2-development`
- **Audit baseline:** `03938815b608f6499f797f2b9ed3ae1c14a614ae`
- **Current verified implementation baseline:** `53ed58bb813066b9b3b1bbff80dd6329c90d2336`

## 1. Purpose

Define exactly what SH-3 persistent replay integrity values prove, which adversaries are in scope, and whether a database writer must be prevented from silently rewriting both a record and its digest.

This document is a design and acceptance plan. **Option B is selected.** It does not add code, change the database schema, provision keys, rotate keys, or authorize a production operation.

## 2. Verified current implementation

The current implementation uses unkeyed SHA-256 digests over canonical data. The digest is stored alongside the protected record in the same SQLite database. An actor with sufficient write access to the database can alter a record and recompute the digest. Therefore these values provide consistency/corruption detection, not authenticity against a malicious database writer.

The reviewed digest surfaces include:

- `infrastructure/security/evidence.py`: `EvidenceRecord` canonical payload digest and `verify()`.
- `infrastructure/security/persistent_store.py`: replay Stage input fingerprints and persisted Stage result integrity.
- `infrastructure/security/persistent_operation_store.py`: operation input fingerprints, Action/Rollback result integrity, and Action Plan integrity.

Do not describe these SHA-256 values as signatures, authenticated evidence, or tamper-proof storage.

## 3. Threat-model decision gate

The design decision is **Option B — Authenticated persistent records**. Option A is retained below only as the rejected alternative and is not the implementation target. The threat model and assumptions for the selected option are binding design inputs.

### Selected threat model and attacker capabilities

The following database-only attacker is in scope:

- Can read, copy, insert, update, and delete SQLite rows and database sidecar/backup files to which the attacker has filesystem access.
- Can alter a stored record and recompute any unkeyed SHA-256 digest or database-local metadata.
- Can attempt to substitute records, tags, key IDs, tenant/cycle/parent identifiers, and persisted schema or policy values.
- Cannot obtain HMAC key material, compromise the external key-provider trust boundary, or invoke an authorized signing operation for attacker-chosen content.

The following are not protected by HMAC alone and must be assessed as separate threats: compromise of the SH-3 runtime/application process, compromise of the host or its administrator/root account, compromise of the deployment identity or key provider, source/build pipeline compromise, and misuse of an authorized signing interface. The deployment threat model must state how these capabilities are controlled. A database-controlled flag must never be sufficient to enable or downgrade authenticated mode.

The key-provider boundary must prevent a database writer from using the signing service as an unrestricted signing oracle. Signing authorization must be bound to the SH-3 workload identity, permitted purpose/domain, and deployment policy.

### Option A — Bounded local-storage threat model (rejected for this project direction)

Accept the existing SHA-256 mechanism only for accidental corruption and isolated/uncoordinated modification detection. Explicitly exclude an actor who can rewrite the SQLite database and recompute its hashes from the authenticity threat model.

Required compensating controls:

- Restrict database and backup write access using least-privilege OS ACLs.
- Keep production database files outside the source checkout.
- Protect backups and audit exports in a separate access boundary.
- Document that a privileged database writer can forge the current digest fields.
- Do not claim authenticity against a database writer.

This option minimizes code and key-management complexity but does not meet a threat model that includes malicious database writers.

### Option B — Authenticated persistent records (selected)

Add HMAC-SHA-256 authentication using key material held outside SQLite and outside the repository. Use a key-provider abstraction so local tests, deployment secret stores, and future KMS integrations are replaceable.

Required design properties:

- Use HMAC-SHA-256 as the initial algorithm. Use Python's standard-library `hmac` and `hashlib` for the software implementation unless a separately justified HSM/KMS-backed HMAC operation is selected. Do not introduce asymmetric signatures without a documented requirement.
- The minimum key strength is 256 bits of cryptographically random key material. Key IDs are public identifiers, not secrets. Key generation, storage, backup, and access policy belong to the external provider/deployment boundary.
- Prefer a provider interface that exposes `active_key_id(purpose)`, `sign(key_id, message)`, and `verify(key_id, message, tag)` operations. Keep software/local test providers replaceable by a secret-manager, HSM, or KMS adapter. Provider errors must fail closed; do not fall back to an unkeyed digest.
- The provider must authorize signing only for the SH-3 workload identity and approved integrity purpose. A DB writer must not be able to call a general-purpose signing endpoint with arbitrary bytes.
- The authenticated envelope must identify the algorithm, authentication-format version, canonicalization version, key ID, and tag. These fields are metadata only; key material must never be persisted.
- The signed message must use an unambiguous, length-delimited or canonical-envelope encoding. Include a fixed SH-3 persistent-replay domain prefix, record kind, format/canonicalization versions, stable record identity, tenant identity when applicable, cycle identity, parent identity, operation kind, and all semantic fields whose alteration must be detected. Include the key ID in the authenticated envelope/message to prevent metadata substitution.
- Persist the authentication metadata atomically with the protected record. Do not perform an unbounded remote key-provider call while holding `BEGIN IMMEDIATE`; prepare the tag before the write transaction where possible, then commit the record and tag atomically with the existing generation/owner compare-and-set checks. If a provider requires in-transaction calls, document and test its timeout, locking, and failure semantics.
- Key rotation uses a new active key for new writes while retaining verification access to prior key IDs for the full record, backup, and restore retention period. Revocation and emergency key compromise procedures must be documented.
- Loss of a required verification key is a fail-closed integrity/readiness failure. There is no automatic fallback to `sha256:` verification in authenticated mode.
- Do not store raw key bytes in SQLite, database snapshots, source control, logs, diagnostics, or ordinary application configuration.
- Use `hmac.compare_digest()` for tag comparison.
- Authenticate canonical bytes with explicit domain separation, record kind, format version, stable record identity, and relevant tenant/cycle/parent identity. Prevent digest/tag reuse across evidence, Stage, Action, Rollback, and Action Plan domains.
- Define a strict, versioned canonicalization format: require string object keys; reject duplicate JSON keys, unsupported objects, non-finite floats, and ambiguous coercions; define datetime normalization; use fixed UTF-8 and deterministic JSON separators/order; and maintain cross-version golden test vectors. Do not reuse `EvidenceRecord._normalize()` unchanged because it stringifies arbitrary keys/unknown objects.
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
- If the chosen format changes persisted columns or schema metadata, add a new explicit schema migration to schema version 2 (or a later ordered version), a verified pre-migration backup, transactional DDL, restore/rollback tests, and a compatibility window. Do not repurpose G-C's schema version 1 in place.
- In authenticated mode, the default is to reject legacy unkeyed `sha256:` records as authenticated evidence. A narrowly scoped, externally configured legacy-read mode may be provided for reviewed transition/recovery only; it must preserve the legacy label, must not permit a database value to enable it, and must never claim historical authenticity. New writes in authenticated mode must use HMAC.
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
| Claim/lease/ownership state | Structural checks, transactions, owner tokens, and generation fencing | Authenticate security-relevant lifecycle state or replace mutable state with authenticated transitions; prove stale-owner and generation fencing remains intact |

Do not implement only `EvidenceRecord` HMAC while continuing to describe the entire replay ledger as authenticated. Scope every claim to the exact protected data.

## 6. Proposed implementation boundaries for Option B

If Option B is selected, prepare a separate implementation PR with the following layers:

1. `infrastructure/security/integrity.py`: typed protocol and immutable authentication metadata; standard-library HMAC implementation.
2. Key-provider boundary: active signing key and lookup by key ID; no concrete secret-manager dependency until deployment target is selected.
3. Canonicalization: versioned, domain-separated serialization shared by Evidence, Stage, Operation, and Action Plan records.
4. Persistence adapters: explicit integrity-policy injection; no hidden global key state.
5. Readiness: report authentication mode and fail closed according to externally configured policy. A database-controlled flag alone must not be able to downgrade authenticated mode.
6. Backup/restore: preserve tags and require the matching verification key IDs at restore/readiness time. The backup is not independently trusted merely because record tags verify; freshness/rollback policy is separate.
7. Migration: add an explicit schema version 2 (or later) migration when persistence layout changes; preserve legacy SHA-256 values exactly and mark them as legacy; no implicit re-signing or authenticity upgrade.
8. Operations: define secret provisioning, least privilege, workload identity, key rotation, revocation, backup/restore access, recovery, and loss-of-key behavior.
9. Claim and lease lifecycle: include the security-relevant state in the inventory and protect ownership/generation transitions without weakening existing atomic compare-and-set and fencing behavior.
10. Provider execution: define latency, timeout, availability, and transaction boundaries so an external provider cannot create unbounded SQLite write-lock durations.

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

## 8. Security guarantees and explicit non-guarantees

The selected HMAC design is intended to provide **record authenticity/integrity against a database-only writer** who cannot access or invoke the authorized key-provider signing boundary. It is not a general tamper-proof database design.

HMAC by itself does not detect or prevent:

- Deletion of a valid authenticated record when no trusted external inventory proves that the record should exist.
- Truncation or omission of otherwise valid rows.
- Reordering where order is not part of the authenticated semantic identity.
- Replay of a previously valid record or rollback to an older valid database/backup snapshot.
- Denial of service, database encryption/ransomware, or loss of the verification key.

Before production claims include ledger completeness or freshness, design and test a separate trust anchor outside SQLite, such as an externally stored monotonic sequence/checkpoint or independently protected append-only audit log. A hash chain stored only in the same SQLite database is not sufficient against a writer who can roll back that database. If rollback/completeness protection is not deployed, explicitly exclude it from the guarantee and require an owner-approved risk decision before production approval.

Do not use phrases such as “tamper-proof,” “immutable,” “exactly once,” or “rollback-proof” unless a separately tested control proves that exact property.

## 9. Exit criteria

G-D is complete only when:

- The responsible owner records the selected threat model and accepted attacker capabilities.
- Every persisted integrity field is inventoried and has an explicit assurance level.
- The selected option's code and operational requirements are implemented and reviewed.
- Legacy record semantics and key rotation/recovery behavior are documented.
- Tampering tests prove the exact stated guarantee; no broader claim is made.
- Ruff, Mypy, focused tests, full pytest, and backup/restore compatibility checks pass.
- Any required schema migration is explicit, backed up, transactional, and separately approved.

## 10. Recommended next action

Option B has been selected. The next implementation design must inventory all persisted fields, finalize the strict authenticated-envelope/canonicalization format, define the external key-provider contract and workload authorization, and specify the legacy-read and schema-version-2 migration policy. Decide separately whether production requires an external monotonic checkpoint/append-only trust anchor for deletion, truncation, and snapshot rollback detection.

No production database migration, data re-signing, or key rotation is authorized by this plan.
