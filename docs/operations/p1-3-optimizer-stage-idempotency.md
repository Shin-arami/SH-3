# P1-3 — Persistent Optimizer Stage Idempotency Contract

## Scope

P1-3 adds a durable Stage boundary around `LearningOptimizerBoundary.request()`.
It reuses the P1-1 SQLite Stage execution ledger and the active parent Replay Claim;
it does not create a second ledger or change the default non-persistent kernel path.

## Stage identity

- Stage name: `learning_optimizer.request.v1`.
- Contract version: `learning-optimizer-v1`.
- Parent identity: `cycle_id` and the parent replay `cycle_fingerprint`.
- Input fingerprint: canonical JSON containing `learning_record_id`, `domain`, `success`,
  `score`, `strategy`, and learning-result `metadata`.
- The derived Stage idempotency key is stable across parent claim generations and replay
  event causation changes. Owner tokens, generation, attempt counters, timestamps, and
  event lineage are not part of the key.

## Execution protocol

1. The coordinator forwards the active parent claim identity, owner token, and generation.
2. The optimizer boundary rejects incomplete claim metadata when a Stage Store is configured.
3. `begin()` validates parent ownership and lease before optimizer work starts.
4. A completed Stage restores its validated JSON result and does not call the optimizer again.
5. A claimed Stage runs the optimizer and update boundary with the same stable idempotency key.
6. The normalized optimizer result is committed through `complete()` before it is returned.
7. Completion is fenced by the parent claim generation, owner token, and lease in the Stage Store.

## Downstream idempotency

The optimizer backend must accept `idempotency_key`. `SystemOptimizer` passes it into the
execution context used by optimization actions. `OptimizationUpdateBoundary` derives a stable
update request identity from the key and forwards it to `execute_actions` in that context.
Custom backends and actions that perform external side effects must persistently deduplicate
that key (or commit the side effect and completion record in one transaction).

The SQLite Stage ledger alone cannot guarantee exactly-once execution of arbitrary external
side effects. If a process crashes after a downstream side effect but before Stage completion,
the next generation can call the backend again with the same key. Without downstream
idempotency, that side effect may occur more than once.

## Failure policy

As with P1-2, optimizer exceptions are represented as failed `LearningOptimizationResult`
values and are persisted as completed Stage results. A retry using the same Stage identity
restores that failure rather than automatically rerunning a transiently failing optimizer.
A separate retry policy must use an explicitly defined new attempt identity or recovery path.

## Compatibility

- `SH3Kernel()` without a persistent Stage Store keeps the legacy behavior.
- Persistent optimizer construction requires a backend whose `optimize()` accepts
  `idempotency_key` or `**kwargs`.
- Persistent optimizer events cannot bypass coordinator claim metadata; persistent requests
  are entered through the coordinator-facing boundary method.
- The supported persistence deployment remains the P1-1 local/file-backed SQLite model.

## Required verification

- Completed optimizer Stage restores without reoptimizing after a fresh boundary is created.
- Event causation changes do not change the Stage idempotency key.
- A crash between optimizer execution and Stage completion can be retried under a newer
  parent generation with the identical downstream key.
- Missing claim metadata and a backend without idempotency-key support fail closed.
