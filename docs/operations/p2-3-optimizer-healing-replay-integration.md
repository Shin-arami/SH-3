# P2-3 窶・Optimizer Healing Replay Integration

## Scope

P2-3 carries the active parent replay claim through `OptimizerHealingBoundary` into its nested `RecoveryStrategyBoundary` and `RecoveryExecutionBoundary`. It does not introduce a separate durable stage for the orchestration wrapper; the nested recovery stages remain the durable execution contracts established by P2-1 and P2-2.

## Stable input contract

When the optimizer fails during a persistent learning cycle, `LearningClosedLoopCoordinator` supplies:

- cycle ID and cycle fingerprint;
- current claim owner token and generation;
- stable stage input containing source `optimizer`, learning result ID, optimizer ID, learning-record ID, optimization request ID, and optimizer failure details.

The input excludes request IDs derived from trace/correlation context, event IDs, owner tokens, claim generations, and wall-clock timestamps from the stage fingerprint. Claim owner and generation are passed separately to the nested stores for fencing. The selected recovery strategy is added by P2-2 to the execution-stage input, so a strategy change creates a distinct execution stage.

## Event propagation

`OptimizerHealingRequest.to_dict()` and `from_dict()` preserve the complete replay metadata. Therefore, direct execution and the `OptimizerHealingRequested` event-bus path pass the same replay claim into strategy selection and recovery execution.

Persistent metadata is all-or-nothing. Supplying partial metadata is rejected. When replay metadata is supplied, both recovery strategy and execution boundaries must be configured; otherwise healing fails closed rather than silently falling back to nonpersistent execution.

## Replay behavior

On a repeated optimizer-healing attempt under a newer valid claim generation, the strategy stage restores its completed selection and the execution stage restores its completed typed result. The underlying recovery backend is not called again for a completed execution stage. The wrapper may reconstruct a new in-memory `OptimizerHealingResult` and event context, but it reuses the durable nested outcomes.

Calls without replay metadata retain legacy behavior. Kernel construction already shares one `SQLiteReplayStageStore` between the two nested boundaries; P2-3 relies on that shared store.

## Failure and exactly-once limits

P2-1 and P2-2 persist completed strategy and execution outcomes, including failures. A cached failed execution is replayed as the same failure; claim-generation advancement alone does not retry a completed stage. Retry policy must explicitly produce a new stage identity or use an appropriate higher-level recovery policy.

The Stage Store does not make external side effects exactly once. If a recovery backend performs an external side effect and the process stops before the execution stage completion is committed, a later claim generation may invoke the backend again. Backends with external effects must use a stable downstream idempotency key or a transaction that atomically couples the side effect with stage completion.

## Verification

The P2-3 tests verify request event serialization, replay metadata forwarding to nested strategy and execution boundaries, rejection of partial metadata, and propagation from the persistent learning coordinator. Run the focused optimizer-healing tests, the P2-1/P2-2 recovery tests, Ruff, Mypy, and the full test suite before committing.
