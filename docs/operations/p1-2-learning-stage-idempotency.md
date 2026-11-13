# P1-2: Persistent Learning Stage Idempotency

## Purpose

Connect the P1-1 replay stage execution ledger to the Cognitive Learning
execution path. A logical Learning stage uses a stable `ReplayStageKey` that
does not include the replay claim generation or owner token.

## Stage identity

The stage name is `cognitive_learning.record.v1`. Its input identity contains
the stable Learning input and contract identifier. The parent cycle identity
and fingerprint are supplied by `LearningClosedLoopCoordinator`.

The coordinator passes the active claim cycle ID, fingerprint, owner token,
and generation to `CognitiveLearningBoundary`.

## Execution protocol

1. `CognitiveLearningBoundary.record()` validates that complete claim metadata
   is present when a persistent stage store is configured.
2. It calls `SQLiteReplayStageStore.begin()` before publishing or executing
   the Learning request.
3. A completed stage restores its serialized `CognitiveLearningResult`
   without calling the Learning backend again.
4. A claimed stage calls the backend with the same stable
   `idempotency_key`.
5. The result, including a failed Learning result, is stored with
   `SQLiteReplayStageStore.complete()`.
6. A later generation can reuse the completed result. An unfinished stage
   remains subject to the parent claim's generation fencing.

### Failed-result finality

An exception raised by the Learning backend is converted by
`CognitiveLearningBoundary` into a failed `CognitiveLearningResult`. That
failure result is persisted as a completed Stage, just like a successful
result. A later generation with the same Stage identity therefore restores the
same failure without invoking the backend again. Transient backend exceptions
are not automatically retried under the same Stage identity. A retry policy
for transient failures requires a separately designed contract and state
transition; it must not be inferred from the Stage takeover mechanism.

## Native LearningLoop behavior

`LearningLoop.run()` accepts the optional `idempotency_key`. Within one
LearningLoop instance, completed results are cached by that key so a retry
after a successful backend return does not repeat Policy, Planner, or Memory
updates. Memory keys are derived from the stage key, and an existing identical
Memory value is not appended to the timeline again.

The non-persistent `SH3Kernel()` path continues to call Learning without an
idempotency key and retains the legacy Memory key behavior.

## Backend contract and limits

A backend used with `SQLiteReplayStageStore` must accept `idempotency_key`.
A backend that performs durable external side effects must use this key to
deduplicate those effects or participate in the same transaction as the
stage completion record.

The SQLite ledger cannot make an arbitrary external side effect and its own
completion write atomic. A crash after an external effect but before
`complete()` can cause a later generation to invoke the backend again.
Passing a stable key enables downstream deduplication; it does not create
Exactly-once semantics by itself.

The native `LearningLoop` result cache is process-local. The SQLite Stage
Store remains authoritative for completed-stage replay across Runtime
restarts.
