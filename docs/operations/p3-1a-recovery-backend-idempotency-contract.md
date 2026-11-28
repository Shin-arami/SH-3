# P3-1A - Recovery Backend Idempotency Contract

## Purpose

Persistent recovery execution already claims a stable `ReplayStageKey` and
stores its terminal result. P3-1A forwards that same key to the recovery
backend so the backend can deduplicate a side effect if a process stops after
the side effect but before the Stage Store records completion.

## Contract

When `RecoveryExecutionBoundary` is configured with a
`SQLiteReplayStageStore`, its backend `recover_with_strategy` method must
accept a keyword `idempotency_key` or arbitrary keyword arguments (`**kwargs`).
The boundary fails fast during construction if the callable cannot be
inspected or does not expose that capability.

For a persistent execution, the boundary passes the exact
`ReplayStageKey.idempotency_key` to `recover_with_strategy`. The same value is
included in `RecoveryExecutionRequested`, `RecoveryExecutionCompleted`, and
`RecoveryExecutionFailed` event payloads.

The built-in `SelfHealingCore` accepts the key and propagates it to the
selected `RecoveryPlan` action, lifecycle events, and recovery-learning detail.
Its built-in context rebuild clears in-memory context; repeated clearing is
naturally repeatable. Custom recovery actions that perform non-idempotent
external effects must use the supplied key at the system that owns the effect.

Legacy, non-persistent calls do not pass the keyword and remain compatible
with older backends that implement only `(snapshot, strategy)`.

## Backend obligations

Accepting the keyword is a capability declaration, not proof of correct
deduplication. A backend that performs non-idempotent external effects must:

1. Use the supplied key as the stable operation identity at the system that
   owns the effect (or in a durable local inbox/outbox).
2. Persist the key and terminal outcome durably before reporting success.
3. Return the previously recorded outcome for a repeated key.
4. Reject reuse of the same key with semantically different operation input.
5. Retain deduplication records for at least the maximum replay/retry horizon.

A process-local dictionary is not sufficient for cross-restart deduplication.

## Guarantees and limitations

The Recovery Stage Store prevents re-execution after a completed Stage has
been recorded. Forwarding the key allows a capable backend to close the
remaining crash window between performing an external effect and recording
Stage completion.

The Stage Store and an arbitrary external system do not share an atomic
transaction. Therefore SH-3 cannot promise exactly-once external effects for
a backend that merely accepts but ignores the key, or whose deduplication
state is not durable. Such a backend must be treated as not conforming to the
persistent recovery contract.

Failed Recovery Execution results remain terminal at the Stage level under
the existing P2-2 policy; P3-1A does not introduce automatic retries.
