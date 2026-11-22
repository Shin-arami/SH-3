# P3-2C - Durable Recovery Execution Replay Contract

## Scope

P3-2C connects `RecoveryExecutionBoundary` to the P3-2A
`SQLiteReplayOperationStore`. A persistent Recovery Execution Stage has one
independent durable operation row (`operation_kind=action`,
`operation_name=recovery_execution`, `ordinal=0`). The existing Replay Claim
and Recovery Execution Stage remain the authorities for ownership and
Generation fencing.

No database schema migration is introduced. The operation row is stored in
the existing `sh3_replay_operations` table and is included automatically in
the existing SQLite online backup/restore and readiness validation.

## Operation identity

The operation key is derived deterministically from the existing
`recovery_execution.execute.v1` Replay Stage key. Its tenant scope comes from
the current `EventPropagationContext`. Its parent Stage key is the exact
Recovery Execution Stage idempotency key. Its semantic input includes the
stable Recovery Stage input and selected strategy; request IDs, trace IDs,
owners, generations, and timestamps are not operation input.

The Recovery backend continues to receive the original P3-1A
`ReplayStageKey.idempotency_key`, not the new internal Operation Ledger key.
This preserves the backend's downstream idempotency contract across process
restarts and across P3-2C adoption.

## Execution ordering

For a newly claimed persistent Recovery Execution Stage:

1. Claim the parent Stage under the current Replay Claim owner/generation.
2. Claim the Recovery operation in `SQLiteReplayOperationStore`.
3. If the operation is already completed, restore its integrity-verified result
   and complete the parent Stage without invoking the backend.
4. Otherwise invoke `recover_with_strategy` with the stable Stage idempotency
   key.
5. Persist both successful and failed terminal outcomes in the Operation
   Ledger.
6. Complete the Recovery Execution Stage using the exact same result envelope.

The Operation Ledger is therefore committed before the parent Stage. If the
process stops after Operation Ledger completion but before Stage completion,
a newer valid claim generation takes over the Stage, reads the completed
operation, and finalizes the Stage without invoking the backend again.

Previously completed Recovery Execution Stages created before P3-2C remain
readable through the original Stage Store result path. They do not require a
backfilled Operation Ledger row.

## Error and EventBus propagation

Persistent Recovery execution is dispatched synchronously with the private
owner/generation context rather than passing that context through EventBus
request handlers, whose delivery layer records subscriber exceptions instead
of raising them to the publisher. Accordingly, the persistent synchronous path
does not publish the `OptimizerHealingRequested` or
`RecoveryExecutionRequested` START events. Non-ledger legacy requests retain
the previous EventBus request behavior.

When a Recovery backend execution reaches a normal terminal outcome and an
event publisher is configured, the terminal Event object is prepared before
finalization so its event ID can remain the result's causation ID. The publisher
is invoked only after its Operation Ledger outcome and parent Stage have both
been persisted successfully. If no publisher is configured or event
preparation fails, no Recovery Execution terminal event is emitted; the durable
Operation and Stage records remain the source of truth. A process can still
stop after both commits and before the publish call; this contract does not
provide a transactional event outbox or guarantee terminal event delivery
across that final crash window. Publisher delivery failures are best-effort
notifications and do not undo the committed Recovery outcome. When a previously
completed Operation or Stage is restored, `RecoveryExecutionBoundary` returns
the restored result directly and does not republish a Recovery Execution
terminal event. The enclosing Optimizer Healing request can publish
`OptimizerHealingCompleted` or `OptimizerHealingFailed` when it reaches its
own normal terminal path. Consumers must treat the durable replay records as
the source of truth rather than relying only on event delivery.

An Operation Ledger claim, Operation result restoration, Operation completion,
or parent Stage finalization failure raises `DurableOperationPersistenceError`
and propagates to the caller. It is not converted into an ordinary
Recovery/Healing failure and does not emit the corresponding normal
Recovery/Healing terminal event. This preserves the distinction between a
confirmed durable outcome and a persistence failure whose outcome cannot be
safely reported as complete.

## Failure and exactly-once boundary

A callback exception is recorded as a terminal failed Operation result, in line
with P2-2's same-Stage terminal failure policy. Advancing the claim generation
does not retry a completed failure under the same operation identity.

The Operation Ledger does not share an atomic transaction with arbitrary
external Recovery effects. A process may stop after an external effect but
before the operation result is committed. The Recovery backend must therefore
honor the unchanged P3-1A idempotency key at the system that owns the effect,
persist the key and outcome durably, return the prior outcome for repeats, and
reject conflicting input. SH-3 does not claim universal exactly-once external
effects.

## Compatibility

- Non-persistent `SH3Kernel()` and direct Recovery calls retain their existing
  in-memory behavior.
- A `RecoveryExecutionBoundary` configured with only a Stage Store retains
  P2-2 behavior.
- Existing completed Stage rows remain compatible and are not migrated.
- Optimizer Action/Rollback rows and P3-2B's immutable Action plan are
  unchanged.
- Existing backup, restore, readiness, and JSON report schemas are unchanged.

## Validation

P3-2C tests cover successful durable Recovery results, recovery after an
interrupted Stage finalization, persisted terminal failures, propagation of
Operation Ledger write failures through Healing and the closed-loop
Coordinator, and legacy Stage-only behavior.

Run:

```powershell
& $Python -m pytest -q tests\kernel\test_persistent_recovery_execution_ledger.py tests\kernel\test_recovery_execution_boundary.py tests\kernel\test_optimizer_healing_boundary.py
& $Python -m pytest -q tests\kernel\test_persistent_learning_optimizer_healing_restart.py tests\kernel\test_persistent_optimizer_action_ledger.py
& $Python -m ruff check infrastructure kernel tests
& $Python -m mypy infrastructure\security\persistent_operation_store.py infrastructure\security\persistent_replay_ops.py infrastructure\security\persistent_replay_runtime.py kernel\replay_execution_context.py kernel\recovery_execution_boundary.py kernel\optimizer_healing_boundary.py kernel\learning_feedback_loop.py kernel\core.py
& $Python -m pytest -q
 git diff --check
```

P3-2C does not stage, commit, or push files.
