# P3-2G — Persistent Replay Remediation Status

- **Status date:** 2026-11-28 (JST)
- **Repository:** `Shin-arami/SH-3`
- **Branch:** `v2.2-development`
- **Verified branch head:** `53ed58bb813066b9b3b1bbff80dd6329c90d2336`
- **Baseline audit:** `p3-2g-persistent-replay-production-readiness-audit.md`
- **Purpose:** Track remediation against the immutable 2026-11-27 audit baseline.

## 1. Current decision

**Production readiness remains NOT APPROVED.** The P0 findings G-01 and G-02 and the P1 finding G-03 are closed by merged remediation work. Applicable P1 findings G-04, G-05, G-06, G-08, G-09, and G-12 remain open. G-13 remains conditional on production external-backend scope. G-11 is partially mitigated but remains open until the dependency/build/test/release inventory is audited completely.

This status record does not replace the original audit evidence or imply that all P1 risks have been accepted.

## 2. Finding status

| Finding | Severity | Status at 2026-11-28 | Evidence / remaining work |
|---|---:|---|---|
| G-01 — Branch protection and automated CI/Security | P0 | **CLOSED** | `v2.2-development` reports protected=true; required checks are `CI Required Checks` and `Security Required Checks`. CI/Security workflows include the active branch, Linux/Windows Python 3.12, and immutable Action SHAs. PR #2 produced green CI/Security and platform checks. |
| G-02 — Durable Action compatibility fingerprinting | P0 | **CLOSED** | PR #1 merged at `b3950db252acc1c7a379100795309cf3d754c8c2`. Persisted Action Plan v2 binds Action name, contract ID, implementation version, rollback version, and replay policy; mismatches fail closed. See `p3-2g-g-b-action-contract-compatibility.md`. |
| G-03 — Database schema lifecycle | P1 | **CLOSED** | PR #2 merged at `53ed58bb813066b9b3b1bbff80dd6329c90d2336`. Dedicated `sh3_schema_metadata.schema_version`, explicit 0→1 migration, verified pre-migration backup, transactional DDL, fail-closed Runtime readiness, and explicit version-0 restore-then-migrate regression test are merged. |
| G-04 — Database-writer authenticity | P1 | **OPEN — Option B selected; implementation pending** | Adopt externally keyed HMAC-SHA-256 for authenticated persistent records. The DB-only writer is in scope; key-provider compromise and runtime/host compromise are separate threats. HMAC does not by itself detect deletion, truncation, or rollback to a previously valid snapshot. See `p3-2g-g-d-integrity-trust-boundary.md`. |
| G-05 — Retention and coordinated pruning | P1 | **OPEN** | Define retention classes, coordinated archive/prune invariants, maintenance locking, audit trail, and scale benchmarks. |
| G-06 — Ignore rules for database artifacts | P1 | **OPEN** | `.gitignore` still lacks explicit database, SQLite sidecar, backup, snapshot, and local `var/` exclusions; add repository artifact guard. |
| G-07 — Security reporting policy | P2 | **OPEN** | Add a real `SECURITY.md` and verify the private reporting channel before publishing contact instructions. |
| G-08 — End-to-end tenant isolation | P1 | **OPEN** | Declare shared-database versus per-tenant-database model and prove it across claims, stages, evidence, operations, plans, events, and recovery. |
| G-09 — Forced process-termination windows | P1 | **OPEN** | Add subprocess termination/restart tests for the audit's four orchestration boundaries and verify deduplication/fencing. |
| G-10 — Durable notification delivery | P2 | **OPEN — best-effort contract** | Current notifications remain best effort. Keep this documented unless durable at-least-once delivery is explicitly required; then design a transactional Outbox. |
| G-11 — Dependency and workflow supply-chain audit | P2 | **PARTIALLY MITIGATED / OPEN** | Workflow Actions are SHA-pinned and active-branch security checks run. The dependency audit still only scans the empty `requirements.txt`; `pyproject.toml` build requirements and the actual CI/test/release toolchain need an authoritative inventory and audit. |
| G-12 — Production operational controls | P1 | **OPEN — deployment evidence required** | Approve RPO/RTO, backup cadence/retention, off-host protection, encryption/key handling, ACLs, restore drills, disk/WAL/lock monitoring, and evidence bundle. |
| G-13 — External backend idempotency | P1 conditional | **CONDITIONAL / OPEN** | Require adapter-specific tests and operational proof for every real production backend; otherwise document that no such backend is in scope. |

## 3. G-D security decision

- **Selected design:** Option B — authenticated persistent records using HMAC-SHA-256.
- **In-scope attacker:** an actor able to read and modify the SQLite database and its local artifacts, including changing records and recomputing unkeyed SHA-256 digests, but unable to obtain HMAC keys or invoke authorized signing operations.
- **Explicit limitation:** HMAC authenticates protected record content and bound identity. It does not alone prove database freshness/completeness or detect deletion, truncation, replay of a previously valid snapshot, or rollback. Those guarantees require a separate external monotonic checkpoint or append-only trust anchor, or an explicitly approved risk exception.
- **Implementation status:** not started. No keys, schema changes, migrations, re-signing, or production operations are authorized by this decision record.

## 4. Merged remediation evidence

### G-A — Repository governance and CI/Security

- The `v2.2-development` branch currently reports `protected: true`.
- Required status checks: `CI Required Checks`, `Security Required Checks`.
- `.github/workflows/ci.yml` and `.github/workflows/security.yml` include `v2.2-development` for push and pull-request events.
- CI matrix: `ubuntu-latest` and `windows-latest`, Python `3.12`.
- Third-party GitHub Actions are pinned to immutable commit SHAs.
- PR #2 checks on head `6142d2490365b3303c86a1f412f9f53db9486c26`: required CI, required Security, Windows, Ubuntu, Dependency Audit, CodeQL, and Advanced Security all succeeded.

### G-B — Persisted Action compatibility

- PR: https://github.com/Shin-arami/SH-3/pull/1
- Merge commit: `b3950db252acc1c7a379100795309cf3d754c8c2`
- Contract metadata and Action Plan v2 are documented in `p3-2g-g-b-action-contract-compatibility.md`.

### G-C — Schema lifecycle

- PR: https://github.com/Shin-arami/SH-3/pull/2
- Merge commit: `53ed58bb813066b9b3b1bbff80dd6329c90d2336`
- Feature commits: `40e0f4ace0cbf8a99247e9c8a1bd5bf3a22c4704`, `6142d2490365b3303c86a1f412f9f53db9486c26`.
- Local post-merge verification on Python 3.12: Ruff passed; Mypy reported no issues in 423 source files; full pytest reported 1,436 passed.
- Git working tree was clean and local `v2.2-development` matched `origin/v2.2-development` after fast-forward to the merge commit.

## 5. Updated execution priority

1. **G-D — G-04 Integrity trust boundary.** Option B is selected: define the DB-writer threat boundary, external key custody, authenticated-record format, legacy-data policy, and separate rollback/completeness controls before implementing cryptographic code.
2. **G-E — G-05/G-06/G-08 Retention, storage hygiene, tenancy.** Resolve the tenancy invariant before implementing coordinated retention across tenant-scoped rows.
3. **G-F — G-09/G-10 Crash and notification semantics.** Preserve the current best-effort event contract unless a durable delivery requirement is formally accepted.
4. **G-G — G-07/G-12/G-13 Production operations and backend acceptance.** These require verified reporting ownership and deployment/backend evidence, not only unit tests.
5. **G-A residual — G-11 supply-chain inventory.** Complete the dependency inventory and audit coverage; SHA-pinning alone does not close G-11.

## 6. Production approval gate

Production approval remains blocked until every P0 is closed and every applicable P1 is closed or has a documented, owner-approved risk exception with compensating controls. G-12 and G-13 require deployment-specific evidence. No production database migration is authorized by this status document.
