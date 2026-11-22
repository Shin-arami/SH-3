# P3-2D - Durable Recovery Execution Failure Matrix

## Scope

P3-2D hardens the P3-2C Recovery Execution integration by testing failure
boundaries around the Recovery callback, the P3-2A Operation Ledger, the
Recovery Execution Stage, SQLite backup/restore, and terminal EventBus
publication. It introduces no database schema migration and no new durable
table.

The production change is deliberately limited to terminal-event ordering in
`RecoveryExecutionBoundary`. For the P3-2A Operation Ledger path, a terminal
Recovery event is prepared before finalization so its event ID can remain the
result's causation ID, but the event is dispatched only after both the
Operation Ledger result and parent Recovery Stage have been committed. Legacy
non-ledger and Stage-only execution retain their prior event path.

## Failure matrix

| Failure boundary | Durable state after failure | Backend invocation | Recovery terminal event |
|---|---|---:|---|
| Initial Operation claim insertion fails | Parent Stage remains claimed; no new Operation row is inserted (a pre-existing row, if any, remains subject to Store validation) | 0 | Not published |
| Operation completion write / simulated SQLite lock | Parent Stage and Operation remain claimed | 1 | Not published |
| Parent Stage completion after Operation commit | Operation is completed; parent Stage remains claimed | 1 | Not published |
| Completed Operation result integrity failure | Operation remains completed but fails integrity validation; Stage remains claimed | 0 on restore attempt | Not published |
| Backend callback returns a normal failure | Failed terminal result is committed to Operation and Stage | 1 | `RecoveryExecutionFailed` after both commits |
| Backend callback succeeds | Successful terminal result is committed to Operation and Stage | 1 | `RecoveryExecutionCompleted` after both commits |

An Operation claim or persistence exception is raised as
`DurableOperationPersistenceError`. It is not converted into a normal Recovery
failure. The persistent Operation path must not publish a Recovery terminal
event unless the Operation result and parent Stage are both durable.

## Generation takeover and external effects

If the backend returns but the Operation result cannot be committed, the
Operation row and parent Stage remain claimed. A later valid Replay Claim
generation may take over both claims and invoke the backend again with the same
P3-1A Recovery Stage idempotency key. This callback retry is intentional: SH-3
cannot determine whether an arbitrary external effect occurred before the
process or SQLite failure.

The downstream system that owns the external effect must durably deduplicate
the unchanged P3-1A key, return the previous outcome for an exact repeat, and
reject conflicting input. The tests use a separate SQLite-backed fake
external system to demonstrate this contract. They verify that the callback
may be invoked twice while the downstream effect is applied only once. This
is not a universal exactly-once guarantee supplied by SH-3.

## Backup, restore, and integrity

A backup taken after Operation completion but before parent Stage completion
must preserve both states. After restore, readiness must validate the snapshot;
a newer valid claim generation must restore the completed Operation result,
complete the parent Stage, and avoid a second backend invocation.

A completed Operation result with a mismatched canonical JSON integrity value
must fail closed. Recovery must not invoke the backend, finalize the parent
Stage, or publish a Recovery terminal event from that corrupted result.

SQLite lock behavior is covered at the Recovery boundary by deterministic
injection of `sqlite3.OperationalError("database is locked")` during Operation
completion. This verifies error propagation and event suppression at the
integration boundary; it is not a stress test of OS-level SQLite locking.

## Terminal event delivery boundary

Persistent Recovery terminal events are dispatched only after the Operation
Ledger and parent Stage commits. A process can still stop after both commits
and before the EventBus publish call. P3-2D does not add a transactional event
outbox, so terminal event delivery is not guaranteed across that final crash
window. A later restore of an already completed Operation or Stage does not
republish a Recovery terminal event. Consumers must treat the durable replay
records as the source of truth and must not infer durable completion solely
from receiving an event.

The EventBus publisher's existing delivery result is best-effort; this phase
does not claim exactly-once or at-least-once event delivery.

## Compatibility

- No schema migration is introduced.
- The P3-1A Recovery backend idempotency key remains unchanged.
- P3-2A Operation identity, result integrity, and Generation fencing remain
  unchanged.
- P3-2B Optimizer Action/Rollback rows and immutable Action plan remain
  unchanged.
- P3-2C Stage-only and non-persistent Recovery paths retain their existing
  behavior.
- Backup/restore/readiness continue to use the existing SQLite operational
  path.

## Validation

Run:

```powershell
& $Python -m pytest -q tests\kernel\test_persistent_recovery_replay_failure_matrix.py tests\kernel\test_persistent_recovery_execution_ledger.py tests\kernel\test_recovery_execution_boundary.py tests\kernel\test_optimizer_healing_boundary.py
& $Python -m pytest -q tests\kernel\test_persistent_learning_optimizer_healing_restart.py tests\kernel\test_persistent_optimizer_action_ledger.py tests\infrastructure\security\test_persistent_operation_store.py tests\infrastructure\security\test_persistent_replay_ops.py
& $Python -m ruff check infrastructure kernel tests
& $Python -m mypy infrastructure\security\persistent_operation_store.py infrastructure\security\persistent_replay_ops.py infrastructure\security\persistent_replay_runtime.py kernel\replay_execution_context.py kernel\recovery_execution_boundary.py kernel\optimizer_healing_boundary.py kernel\learning_feedback_loop.py kernel\core.py tests\kernel\test_persistent_recovery_replay_failure_matrix.py
& $Python -m pytest -q
 git diff --check
```

P3-2D does not stage, commit, or push files.
