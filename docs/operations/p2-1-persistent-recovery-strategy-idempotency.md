# P2-1 — Persistent Recovery Strategy Selection

## Contract

A recovery strategy selection performed inside a persistent learning closed loop is a durable stage named `recovery_strategy.select.v1`. Its identity is derived from the parent cycle ID and fingerprint plus the stable recovery input supplied by the coordinator (`source`, `result_id`, exception type, and exception message).

The stage result persists only the selection decision: selected strategy, candidate evaluations, and the `learned` flag. It deliberately excludes attempt-scoped values such as `FailureSnapshot.trace_id`, request ID, event correlation/causation/trace IDs, owner token, and claim generation.

## Replay behavior

When a later claim generation encounters a completed strategy stage, the boundary restores the persisted decision without calling `evaluate_strategies` or `select_strategy` again. It reconstructs the current attempt's request ID, failure ID, creation time, and propagation context, then emits the normal `RecoveryStrategyEvaluated` and `RecoveryStrategySelected` events with `replayed=true` and the durable idempotency key.

When the stage is claimed but not completed, the current claim owner evaluates and selects the strategy, then commits the selection output through `SQLiteReplayStageStore.complete`. The Stage Store fences this completion with the current parent claim owner token, generation, and lease.

## Compatibility boundaries

Direct `SH3Kernel.recover()` calls and other callers that do not provide replay-claim metadata continue to use the existing in-memory path. Supplying partial replay-claim metadata is rejected. Optimizer Healing's nested strategy selection is intentionally not wired to this stage in P2-1; that caller integration is reserved for P2-3.

## Guarantee boundary

This stage prevents repeated strategy evaluation and selection for the same logical recovery input after a completed stage has been persisted. It does not make the subsequent recovery execution exactly once; persistent recovery execution is the separate P2-2 stage. Event delivery is not an outbox guarantee, so event consumers should use the emitted idempotency key where duplicate delivery matters.
