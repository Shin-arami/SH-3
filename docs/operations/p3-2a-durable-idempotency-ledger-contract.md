# P3-2A - Durable Idempotency Ledger Contract

## Scope

P3-2A adds a durable SQLite ledger for one optimizer Action or its compensating
Rollback. It reuses the existing persistent replay database and its SQLite
connection, transaction, claim, and stage infrastructure. It does not change
Action execution behavior; wiring `SystemOptimizer` to this store is P3-2B.

## Compatibility and lifecycle

The new `sh3_replay_operations` table is additive. Existing databases without
the table remain readable by the read-only readiness check. The persistent
runtime factory and explicit first-use provisioner create the table only after
an existing database has passed its pre-initialization readiness check. The
store requires the existing `sh3_replay_claims` and
`sh3_replay_stage_executions` tables and uses the same resolved database path.

A malformed operation table is not repaired automatically. If the optional
table already exists, readiness validates its schema and rows before the
runtime opens its adapters. Backup and restore continue to use SQLite's online
backup path; readiness validates the operation table in a restored snapshot.

## Operation identity

`ReplayOperationKey` records:

- optional `tenant_id` scope (`None` is represented by the reserved empty
  namespace in SQLite);
- caller-supplied stable `idempotency_key`;
- parent replay `cycle_id` and `cycle_fingerprint`;
- existing optimizer `parent_stage_key`;
- operation kind (`action` or `rollback`), action name, and ordinal;
- optional parent Action operation key for Rollback;
- canonical SHA-256 `input_fingerprint`.

The database primary key is `(tenant_scope, idempotency_key)`. The input
fingerprint is deliberately not part of that key. Reusing a key in the same
tenant namespace with a different cycle, stage, operation identity, parent, or
input fingerprint raises `ReplayOperationConflictError`; it must not create a
second operation record. The empty tenant namespace is global and must only be
used with globally unique keys.

Action and Rollback have separate rows and separate keys. A Rollback row must
reference an existing, completed Action row in the same tenant, cycle, parent
stage, action name, and ordinal. A Rollback cannot begin while its parent
Action is missing or unfinished.

## State and fencing contract

The operation state machine is `claimed` to `completed`:

- `begin()` atomically creates a claim for a missing operation.
- A completed operation returns its integrity-verified stored result and is
  not re-executed by the caller.
- A same-generation duplicate claim is reported as busy.
- An unfinished claim can be taken over only by a strictly newer, currently
  valid parent Replay Claim generation.
- `complete()` requires the active parent owner and matching operation owner
  and generation. Stale owners cannot finalize a newer generation.
- Repeating completion with byte-equivalent canonical result data is
  idempotent; a different result for an already completed key is a conflict.

Each mutation uses `BEGIN IMMEDIATE` and validates the parent Replay Claim,
lease, parent Stage identity, and matching Stage owner/generation. A Rollback
also validates its completed Action identity inside the same SQLite
transaction. Results are canonical JSON with a SHA-256 integrity value. Corrupt
or non-canonical results fail closed. An exact repeated `complete()` remains
idempotent while the parent Replay Claim is still active, including after the
parent Stage has been marked completed; a conflicting result is rejected.

A callback failure is represented by a completed result envelope supplied by
the caller; the ledger does not infer retry policy. P3-2B must persist both
successful and failed terminal callback outcomes and preserve
`state_uncertain` for failed compensation.

## Exactly-once boundary

The ledger prevents duplicate local callback execution after a result has been
committed. It cannot atomically commit a remote side effect and this SQLite
record. If a process stops after a remote side effect but before `complete()`,
recovery may invoke the callback again with the same stable idempotency key.
Non-idempotent external callbacks must durably deduplicate that key at the
system that owns the side effect and reject conflicting input. The ledger alone
does not provide exactly-once external effects.

The ledger also does not make in-memory Runtime or Policy mutations durable.
P3-2B must explicitly classify Action replay behavior so restoring a cached
result does not incorrectly imply that an in-memory mutation exists after a
Runtime restart.

## Validation

P3-2A tests cover Store persistence across reopen, same-key input collision,
tenant namespace isolation, concurrent claims, generation takeover and stale
owner fencing, separate Action/Rollback records, parent Action enforcement,
result integrity, readiness compatibility with older databases, runtime /
provisioning wiring, numeric CHECK-constraint rejection, and online
SQLite backup/restore preservation of completed operation results.

Run:

```powershell
& $Python -m pytest -q tests\infrastructure\security\test_persistent_operation_store.py
& $Python -m ruff check infrastructure tests
& $Python -m mypy infrastructure\security\persistent_operation_store.py infrastructure\security\persistent_replay_runtime.py infrastructure\security\persistent_replay_ops.py
```

Then run the full pytest suite and `git diff --check`. P3-2A does not stage,
commit, or push files.
