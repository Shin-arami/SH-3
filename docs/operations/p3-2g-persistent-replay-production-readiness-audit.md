# P3-2G — Persistent Replay Production Readiness Audit

- **Audit date:** 2026-11-27 (JST)
- **Repository:** [Shin-arami/SH-3](https://github.com/Shin-arami/SH-3)
- **Audited branch:** `v2.2-development`
- **Baseline commit:** `03938815b608f6499f797f2b9ed3ae1c14a614ae`
- **Audit type:** Static source, repository-governance, and operational-document review
- **Decision:** **NOT APPROVED for production deployment**

## 1. Executive decision

The persistent replay implementation has substantial durability controls: file-backed SQLite, read-only readiness checks, integrity and foreign-key validation, generation-fenced claims, durable Action/Rollback records, and verified Online Backup API workflows.

Those controls are not sufficient to certify production readiness. Two release blockers remain:

1. The active development branch has no GitHub branch protection, required status checks, or automatic CI/Security workflow coverage.
2. A persisted optimizer Action plan identifies Actions by name but does not bind the plan to the implementation or contract version of each registered Action. A code change under the same name can therefore be incompatible with a previously persisted plan/result.

High-priority lifecycle, tenancy, retention, integrity-trust, process-crash, and deployment-operations controls also need closure or explicit acceptance. This document records the audit evidence and defines acceptance criteria; it does not claim that the findings have already been fixed.

## 2. Scope, evidence, and limitations

### 2.1 Audited baseline

The branch head was verified from GitHub as:

`v2.2-development` → `03938815b608f6499f797f2b9ed3ae1c14a614ae`

The audit reviewed the persistent replay stores and runtime factory, operation-plan serialization, optimizer Action registration, readiness/backup tooling, evidence hashing, recovery event publication, CI and Security workflows, repository ignore rules, and the related Part 11 operational documents.

### 2.2 GitHub governance snapshot

At audit time, GitHub reported:

- Branch `v2.2-development`: `protected: false`.
- Required status checks on that branch: none.
- GitHub Actions workflow runs queried for that branch: `total_count = 0`.
- Combined commit statuses for the baseline commit: an empty status list.
- Repository rulesets endpoint: an empty list.

The branch endpoint itself reports the branch as unprotected. This is not merely an inability to read the protection settings.

Both `.github/workflows/ci.yml` and `.github/workflows/security.yml` declare push and pull-request branch filters for `main` and `develop`, not `v2.2-development`. Both include manual dispatch; the Security workflow also has a weekly schedule. The CI job currently runs on Ubuntu only and selects Python 3.12 only.

### 2.3 Important limitations

- This is a static review of the repository snapshot. No production deployment, production database, external Recovery Backend, cloud storage, or live operator environment was available for inspection.
- The audit did not execute the repository test suite or reproduce the previously reported local test run. The P3-2F baseline report supplied in the project conversation was **1,424 passed**; it is recorded as user-reported evidence, not as a CI run independently verified by this audit.
- A missing deployment artifact or configuration is classified as **not evidenced**, not proof that the operator has no such control.
- The tenant findings are verification gaps. They are not, by themselves, proof of a cross-tenant data leak.
- Exact-once execution across a local SQLite database and an arbitrary external side effect is not claimed.

## 3. Severity definitions

| Severity | Meaning | Release handling |
|---|---|---|
| P0 | Production release blocker; replay correctness or minimum release governance is not adequately protected | Must close before production approval |
| P1 | High risk to data lifecycle, security boundary, tenant isolation, recovery, or operations | Close before go-live, or record an owner-approved risk exception with compensating controls |
| P2 | Operational hardening or conditional requirement | Close according to release scope; document whether required |

## 4. Findings

### G-01 — Active branch is not protected and is outside automatic CI/Security filters

**Severity:** P0  
**Status:** Open

**Evidence**

- `.github/workflows/ci.yml` filters push and pull-request events to `main` and `develop`.
- `.github/workflows/security.yml` uses the same branch filters.
- The audited branch is reported by GitHub as `protected: false`; no required status checks are configured.
- No workflow run was returned for `v2.2-development` in the queried Actions run list, and the baseline commit has no combined status entries.
- The audited CI workflow runs on Ubuntu only; no Windows matrix job is defined.

**Risk**

Changes can reach the active development branch without the repository's own CI/Security workflows running automatically and without GitHub required-check enforcement. This is especially material because the project has Windows-specific process and SQLite locking tests.

**Acceptance criteria**

1. CI and Security workflows run automatically on push and pull request for the active supported branch(es), including `v2.2-development` while it remains active.
2. CI covers at least Linux and Windows on the supported Python version; platform-specific tests are not silently skipped.
3. Required status checks are configured on the active branch and changes cannot merge without them.
4. Branch protection is verified through GitHub after configuration; the branch endpoint must report protection enabled and the expected required checks.
5. Third-party Actions are pinned to reviewed immutable commit SHAs, with version comments retained for maintainability.
6. A real workflow run on the active branch is green and its status is visible on the branch commit.

### G-02 — Persisted Action plans do not fingerprint Action implementation compatibility

**Severity:** P0  
**Status:** Open

**Evidence**

- `OptimizationAction` carries a name and callable handlers (`apply` and `rollback`), but the persisted plan API receives the ordered Action names.
- `SystemOptimizer._persisted_action_plan()` passes `actions=actions` to `get_or_create_action_plan()`.
- `SQLiteReplayOperationStore.get_or_create_action_plan()` persists a plan in version-1 form as canonical JSON containing `version` and the Action-name list. On retry it returns the saved list.
- Plan integrity is a SHA-256 digest of the serialized plan. It validates stored bytes; it does not establish that the currently registered implementation has the same semantics as the implementation that created it.

**Risk**

An Action can retain its registered name while its implementation or rollback behavior changes between deployments. A restarted Runtime may then restore the earlier plan and reuse a completed operation result under a different implementation contract. Name stability is not implementation compatibility.

**Acceptance criteria**

1. Every durable Action declares a stable contract identifier and an explicit implementation/compatibility version.
2. The persisted Action plan stores the contract identifier and implementation fingerprint/version for every Action and Rollback handler.
3. Operation identity/input fingerprints bind the persisted result to the applicable Action contract, not only the Action name and caller payload.
4. A mismatch fails closed before invoking or reusing an incompatible result. Any upgrade path must be an explicit, versioned migration policy.
5. Tests cover same-version restart reuse, changed implementation under the same name, changed rollback implementation, renamed Actions, removed Actions, and supported migration behavior.
6. Existing durable records have a documented compatibility policy before the new fingerprint becomes mandatory.

### G-03 — Database schema lifecycle has no explicit migration/version mechanism

**Severity:** P1  
**Status:** Open

**Evidence**

- Store constructors create missing tables and indexes with `CREATE TABLE IF NOT EXISTS`.
- `check_database()` verifies the expected tables, columns, constraints, indexes, evidence, and replay invariants; it is a readiness/validation check, not a schema migration runner.
- No `PRAGMA user_version` or equivalent database schema migration mechanism was found in the audited persistent store/readiness code.
- The CLI JSON field `schema_version: 1` describes the emitted report format; it is not the SQLite database schema version.
- The Part 11 operational documentation states that readiness checks do not migrate or repair the database.

**Risk**

A future application version can require a different schema while an older persistent database remains in place. Structural validation may reject it, but there is no explicit, versioned, recoverable migration lifecycle.

**Acceptance criteria**

1. Define an authoritative persistent database schema version.
2. Add ordered, deterministic migrations with an explicit supported source-version range.
3. Run migrations only through an explicit maintenance/provisioning path, not as an implicit side effect of an ordinary readiness check.
4. Require a verified pre-migration backup; apply migrations transactionally where supported.
5. Define failure, rollback, restore, and interrupted-migration recovery behavior.
6. Add compatibility tests for every supported prior schema and tests proving that readiness checks remain read-only.

### G-04 — SHA-256 digests provide integrity checking, not database-writer authenticity

**Severity:** P1  
**Status:** Open — threat-model decision required

**Evidence**

- Evidence records use SHA-256 over normalized, canonical payload data and verify the stored digest on read.
- Replay-operation results and Action plans also use SHA-256 digests over canonical JSON.
- The digest and the protected record are stored in the same SQLite database. No external trust anchor, HMAC key, or signature verification path was identified in the audited implementation.

**Risk**

The digest detects accidental corruption and isolated tampering. An actor with write access to the database can modify a record and recompute its unkeyed digest. The current digest therefore must not be described as proof of authenticity against a database writer.

**Acceptance criteria**

Choose and document one of the following:

- **Bounded threat model:** explicitly state that SHA-256 detects accidental corruption and unauthorized partial modification, but does not authenticate data against an actor who can rewrite the database; restrict database write access and protect backups accordingly.
- **Authenticated evidence:** add HMAC or digital signatures with keys held outside the database, including key provisioning, rotation, revocation, backup/restore, and recovery behavior.

Tests must demonstrate the declared threat model. Do not claim authenticity or tamper-proof storage unless the selected mechanism supports that claim.

### G-05 — Retention, archival, and destructive evidence clearing are not lifecycle-safe

**Severity:** P1  
**Status:** Open

**Evidence**

- The persistent operation store exposes retrieval, claim/complete, Action-plan, and count operations, but no managed retention/pruning API was found.
- The SQLite evidence store's `clear()` method deletes rows from `sh3_evidence_records` only. It does not coordinate deletion or archival of associated replay claims, stages, operation records, and Action plans.
- The Part 11-22 runbook states that the CLI does not implement backup rotation or retention deletion.
- Runtime store creation runs the full readiness check before constructing adapters for an existing database and again after store construction. The check includes SQLite integrity/foreign-key checks and record-level validation.

**Risk**

Unbounded evidence, claim, stage, operation, and plan growth can increase disk use and readiness/startup time. Clearing evidence alone can leave replay history without the terminal evidence required to validate or reconcile it. It is not a safe production reset operation.

**Acceptance criteria**

1. Define retention classes and minimum replay/evidence retention periods.
2. Provide a coordinated archive/prune procedure that preserves claim/evidence/operation referential invariants.
3. Destructive maintenance must run under an explicit maintenance lock or quiesced-writer procedure and be auditable.
4. Prohibit evidence-only clearing as a production reset method, or replace it with a coordinated API.
5. Test retention against completed, pending, expired, reconciliable, and failed replay records.
6. Benchmark readiness/startup checks at expected production database sizes; define acceptable duration and maintenance-window behavior.

### G-06 — Repository ignore rules do not explicitly protect local persistent database artifacts

**Severity:** P1  
**Status:** Open

**Evidence**

The audited `.gitignore` does not explicitly exclude common persistent database artifacts or deployment data directories, including `*.sqlite`, `*.sqlite3`, `*.db`, SQLite `-wal` / `-shm` sidecars, backup files, and `var/`.

**Risk**

A local operational database or backup containing evidence and tenant/operational metadata could be staged and pushed accidentally. The runbook itself recognizes that backups can contain sensitive operational information.

**Acceptance criteria**

1. Add explicit ignore rules for configured local database, SQLite sidecar, backup, temporary snapshot, and local runtime-data paths.
2. Keep production data outside the source checkout where practical.
3. Add a repository check that rejects accidental database/backup artifacts in commits.
4. Document how an operator intentionally exports sanitized test fixtures without committing production data.

### G-07 — README points to a SECURITY.md policy that is absent from the audited branch

**Severity:** P2  
**Status:** Open

**Evidence**

- README's Security section instructs reporters to follow `SECURITY.md`.
- A fetch of `SECURITY.md` from the audited branch returned GitHub 404.

**Risk**

A researcher or user cannot follow a repository-defined vulnerability disclosure process from the audited branch. A security contact or private reporting mechanism must not be guessed or invented.

**Acceptance criteria**

1. Add a real `SECURITY.md` with supported product versions, reporting instructions, expected response process, and disclosure guidance.
2. Configure and verify the actual private reporting path/contact before publishing it.
3. Ensure the documented path is monitored by a responsible maintainer.
4. Keep public issue reporting guidance separate from private vulnerability reporting.

### G-08 — Tenant isolation is not demonstrated end-to-end across every persistence table

**Severity:** P1  
**Status:** Open — invariant clarification required

**Evidence**

- Replay operation and Action-plan records use tenant-scoped composite primary keys.
- Replay claims use `cycle_id` as their primary key.
- Replay stages use `idempotency_key` as their primary key.
- Evidence records use `evidence_id` as their primary key.
- The operation-store tenant tests do not, by themselves, prove end-to-end multi-tenant isolation across claims, stages, evidence, event propagation, and recovery.

**Risk**

If the intended model is a shared database for multiple tenants, globally unique caller-generated identifiers alone may not be an adequate, enforced isolation boundary. If the intended model is one database per tenant or globally unique identifiers, that invariant must be explicit and consistently validated.

**Acceptance criteria**

1. Declare the supported tenancy model: shared database with enforced tenant keys, or physically/logically isolated database per tenant.
2. For a shared database, enforce tenant identity across claim, stage, evidence, operation, and Action-plan relationships, including foreign-key and lookup predicates.
3. For isolated databases, reject cross-database or cross-tenant references at the API boundary and document provisioning rules.
4. Add two-tenant integration tests that deliberately reuse cycle IDs, stage keys, evidence IDs, and operation keys and prove either safe separation or deterministic rejection.
5. Include tenant checks in backup/restore, retention, readiness, and event propagation acceptance tests.

### G-09 — Forced process termination at orchestration crash windows is not established by the reviewed evidence

**Severity:** P1  
**Status:** Open

**Evidence**

P3-2F added meaningful cross-process SQLite contention, lock-timeout, and generation-fencing coverage. The existing Part 11 tests also cover selected crash-window/reconciliation contracts. However, the reviewed evidence does not establish a full end-to-end test that forcibly terminates a worker process at each relevant orchestration boundary.

**Risk**

Exception injection and orderly teardown do not fully model abrupt process termination, OS process death, or a worker disappearing after an external side effect but before its local durable outcome is committed.

**Acceptance criteria**

Add subprocess tests that forcibly terminate the worker and restart the kernel at minimum:

1. After an external effect is accepted but before the operation result is committed.
2. After the operation record is committed but before the parent stage is completed.
3. After stage completion but before terminal notification publication.
4. During claim lease ownership transition/reconciliation.

Each test must assert downstream idempotency/deduplication behavior, owner-generation fencing, durable final state, and absence of duplicate non-idempotent effects.

### G-10 — Recovery event notifications are best-effort, not durably delivered

**Severity:** P2  
**Status:** Open — consumer contract decision required

**Evidence**

- EventBus queue, retry, and dead-letter components are in-memory structures.
- Recovery execution persistence is committed separately from subsequent event publication.
- The recovery boundary calls `publisher.publish(event)` without persisting a transactional outbox record in the same SQLite transaction. Publication exceptions are logged and are not a reason to undo the already committed recovery result.
- The P3-2F decision deferred Outbox work.

**Risk**

A process restart or publisher failure can lose a notification even though the recovery result is durable. This is acceptable only where consumers treat notifications as best-effort hints and can reconcile from durable state.

**Acceptance criteria**

1. Document the notification contract as best-effort and provide a reconciliation/polling path for consumers; or
2. Implement a transactional Outbox whose record commits atomically with the recovery state, with idempotent publication, retry, retention, and consumer deduplication tests.

Do not claim guaranteed event delivery until an Outbox or equivalent durable transport is implemented and tested.

### G-11 — Dependency and GitHub Actions supply-chain auditing is incomplete

**Severity:** P2  
**Status:** Open

**Evidence**

- `requirements.txt` is empty.
- `pyproject.toml` declares no runtime project dependencies, but the build-system requirements include `setuptools>=69` and `wheel`.
- The Security workflow runs `pip-audit -r requirements.txt`; with the audited empty requirements file, this invocation has no declared requirement packages to audit.
- Workflow actions use mutable version tags such as `actions/checkout@v4`, `actions/setup-python@v5`, and `github/codeql-action/*@v3`, rather than immutable commit SHAs.

**Risk**

The current dependency audit does not evidence an audit of the full build/test/release toolchain. Mutable Action tags also make the workflow supply chain less reproducible.

**Acceptance criteria**

1. Maintain an authoritative dependency inventory for runtime, build, test, and release dependencies.
2. Audit the resolved dependency set used by packaging and CI, including build-system requirements.
3. Define supported version ranges and a dependency update process.
4. Pin third-party Actions to reviewed immutable commit SHAs.
5. Verify Security workflow execution on the active branch and retain its results as release evidence.

### G-12 — Production backup, retention, encryption, monitoring, and RPO/RTO controls are documented but not operationally evidenced

**Severity:** P1  
**Status:** Open — deployment evidence required

**Evidence**

The Part 11-21/22 runbooks correctly document the single-host/local-filesystem SQLite boundary, WAL-aware Online Backup API use, backup verification, new-path restore, and operator responsibilities. They also state that the utility does not implement backup rotation, encryption, remote upload, or retention deletion.

The repository cannot demonstrate whether a production deployment has scheduled verified backups, access controls, encryption at rest, off-host copies, restore drills, alert delivery, or accepted RPO/RTO objectives.

**Risk**

A sound backup API is not the same as an operational backup service. A production database can still be lost or unrecoverable if backups are not scheduled, protected, retained, and restored under tested procedures.

**Acceptance criteria**

1. Define and approve RPO, RTO, retention, backup frequency, and restore acceptance objectives.
2. Provide an automated backup schedule using the Online Backup API or an explicitly quiesced procedure.
3. Protect database and backup files using least-privilege filesystem ACLs and encryption at rest; define key access and rotation.
4. Maintain an off-host or otherwise failure-domain-separated backup where required by the deployment threat model.
5. Run and retain periodic restore drills into a new path, followed by readiness checks and replay acceptance tests.
6. Monitor free disk, SQLite lock failures, WAL growth/checkpoint behavior, stale claims, readiness failures, backup age, and restore-test age.
7. Attach actual deployment evidence to the release record; documentation alone does not close this finding.

### G-13 — External recovery side effects require an explicit idempotency contract

**Severity:** P1 if a real external backend is deployed; otherwise conditional  
**Status:** Open — deployment-specific

**Evidence**

The recovery boundary defines backend protocols, including an idempotency-key-capable protocol. The local SQLite ledger cannot atomically commit a transaction with an arbitrary external backend. The Part 11-21 operations matrix explicitly states that repeated external effects must be idempotent, deduplicated downstream, or included in a shared transactional protocol. No concrete production backend configuration or conformance evidence was available in this repository audit.

**Risk**

A worker can perform an external effect and die before the corresponding local result is committed. A retry may repeat that effect unless the downstream system enforces the same idempotency key or provides a compatible transactional protocol.

**Acceptance criteria**

1. For every configured production backend, document whether it supports idempotency keys, deduplication windows, status lookup, and reconciliation.
2. Pass the same stable idempotency key across retries and across process restarts.
3. Define how ambiguous outcomes are queried and reconciled before retrying.
4. Add adapter contract tests for timeout-after-acceptance, duplicate request, backend restart, and delayed status visibility.
5. Do not advertise universal exactly-once semantics. State the actual guarantee and the assumptions required by each backend.

## 5. Existing controls that should be preserved

The audit found the following valuable controls. Follow-up work must preserve these invariants:

- Persistent replay requires a file-backed SQLite database; `:memory:` is rejected.
- A missing database fails closed unless first-time creation is explicitly requested.
- Existing databases are checked before store constructors can run their `CREATE TABLE IF NOT EXISTS` statements, and readiness is checked again after construction.
- The readiness CLI opens the database read-only and checks SQLite integrity, foreign keys, required schema, evidence integrity, and replay consistency.
- The backup/restore implementation uses SQLite's Online Backup API, verifies snapshots, refuses to overwrite an existing destination, and validates the restored database.
- WAL, bounded busy timeout, write transactions, claim leases, owner tokens, and monotonically increasing generations provide useful concurrency/fencing controls.
- The operation ledger keeps Action and Rollback outcomes durable and binds operations to their parent replay claim/stage.
- The runbooks correctly constrain SQLite to a single host and a local filesystem; they warn against copying only the main database file while WAL is active.
- The recovery documentation correctly distinguishes local durable state from arbitrary external side effects.

## 6. P3-2G work packages and priority order

| Work package | Findings | Priority | Completion summary |
|---|---|---|---|
| G-A — CI and repository governance | G-01, G-11 | First | Active-branch automation, platform matrix, required checks, immutable Action pins, green run evidence |
| G-B — Replay implementation compatibility | G-02 | First | Versioned Action contracts/fingerprints, fail-closed mismatch handling, upgrade compatibility tests |
| G-C — Database schema lifecycle | G-03 | Next | Explicit schema version, migration runner, backup/rollback and compatibility tests |
| G-D — Integrity trust boundary | G-04 | Next | Threat-model decision; authenticated evidence if required |
| G-E — Tenant, retention, and storage hygiene | G-05, G-06, G-08 | Next | Lifecycle-safe retention, storage ignores, explicit tenancy model and isolation tests |
| G-F — Crash and notification semantics | G-09, G-10 | Next | Forced-termination tests; explicit best-effort or durable Outbox contract |
| G-G — Production operations and backend acceptance | G-07, G-12, G-13 | Before go-live | Security reporting path, backup/restore evidence, monitoring/RPO/RTO, backend idempotency conformance |

### Recommended execution sequence

1. Close **G-A** and **G-B** first. They protect the change-control path and durable Action replay compatibility.
2. Complete **G-C** and **G-D** before declaring long-term storage and evidence trust guarantees.
3. Complete **G-E** and **G-F** before operating a shared, long-lived replay database or relying on notifications.
4. Complete **G-G** with deployment-specific evidence before production traffic is enabled.

## 7. Production approval checklist

Production approval remains **blocked** until all P0 findings are closed and every applicable P1 finding is either closed or covered by an explicit risk exception approved by the responsible owner.

- [ ] Active branch protection is enabled and required CI/Security checks are green.
- [ ] CI covers Linux and Windows on the supported Python version.
- [ ] Persisted Action plans are bound to implementation/contract compatibility versions.
- [ ] Database schema versions and migrations are explicit and tested.
- [ ] The evidence integrity threat model is documented and implemented.
- [ ] Retention and archive procedures preserve replay/evidence invariants.
- [ ] Database and backup artifacts are protected from accidental source-control inclusion.
- [ ] End-to-end tenant isolation is proven for the declared tenancy model.
- [ ] Forced process-termination recovery tests pass at the required crash windows.
- [ ] Event delivery is explicitly best-effort or backed by a tested transactional Outbox.
- [ ] Dependency and workflow supply-chain controls are in place.
- [ ] Backup/restore, encryption, monitoring, RPO/RTO, and retention have deployment evidence.
- [ ] Every production external backend passes the idempotency/reconciliation contract tests.
- [ ] A release owner reviews and accepts the final evidence bundle.

## 8. Source references

All references below point to the audited `v2.2-development` branch snapshot.

- [CI workflow](https://github.com/Shin-arami/SH-3/blob/v2.2-development/.github/workflows/ci.yml)
- [Security workflow](https://github.com/Shin-arami/SH-3/blob/v2.2-development/.github/workflows/security.yml)
- [Repository ignore rules](https://github.com/Shin-arami/SH-3/blob/v2.2-development/.gitignore)
- [Project dependency/build configuration](https://github.com/Shin-arami/SH-3/blob/v2.2-development/pyproject.toml)
- [Requirements file](https://github.com/Shin-arami/SH-3/blob/v2.2-development/requirements.txt)
- [Optimizer Action model and persisted plan integration](https://github.com/Shin-arami/SH-3/blob/v2.2-development/kernel/system_optimizer.py)
- [Persistent operation store](https://github.com/Shin-arami/SH-3/blob/v2.2-development/infrastructure/security/persistent_operation_store.py)
- [Persistent SQLite stores](https://github.com/Shin-arami/SH-3/blob/v2.2-development/infrastructure/security/persistent_store.py)
- [Persistent replay readiness/backup/restore CLI](https://github.com/Shin-arami/SH-3/blob/v2.2-development/infrastructure/security/persistent_replay_ops.py)
- [Evidence model and SHA-256 verification](https://github.com/Shin-arami/SH-3/blob/v2.2-development/infrastructure/security/evidence.py)
- [Recovery execution boundary](https://github.com/Shin-arami/SH-3/blob/v2.2-development/kernel/recovery_execution_boundary.py)
- [Event bus](https://github.com/Shin-arami/SH-3/blob/v2.2-development/infrastructure/event_bus/event_bus.py)
- [Part 11-21 persistent replay failure matrix](https://github.com/Shin-arami/SH-3/blob/v2.2-development/docs/operations/part11-21-persistent-replay-failure-matrix.md)
- [Part 11-22 persistent replay operations runbook](https://github.com/Shin-arami/SH-3/blob/v2.2-development/docs/operations/part11-22-persistent-replay-operations.md)
- [README security reporting reference](https://github.com/Shin-arami/SH-3/blob/v2.2-development/README.md#security)
- [Audited branch metadata](https://api.github.com/repos/Shin-arami/SH-3/branches/v2.2-development)

---

**Audit conclusion:** P3-2G identifies a strong persistent replay foundation, but the repository snapshot does not meet the controls required for an unqualified production-readiness approval. Close the P0 findings first, then complete or formally accept each applicable P1 finding with deployment evidence.
