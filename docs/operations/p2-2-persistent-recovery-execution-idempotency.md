# P2-2 窶・Persistent Recovery Execution Idempotency

## Scope

`RecoveryExecutionBoundary` can persist the outcome of a recovery execution in the same `SQLiteReplayStageStore` used by the persistent learning/recovery pipeline. The stage name is `recovery_execution.execute.v1`. The Kernel injects the shared store, and `LearningFeedbackLoopCoordinator` forwards the current replay claim metadata to both recovery selection and recovery execution.

## Stage identity

The durable stage key is derived from:

- replay cycle ID;
- replay cycle fingerprint;
- stage name `recovery_execution.execute.v1`;
- the stable recovery input supplied by the coordinator, plus the selected strategy.

Request IDs, trace IDs, timestamps, owner tokens, and claim generations are deliberately excluded from the stage input. The claim owner and generation are passed separately to `begin` and `complete` so the underlying store enforces current parent-claim ownership and generation fencing. A strategy change produces a different execution stage.

## Persisted result contract

The result payload has schema version 1 and stores success/failure, JSON-compatible result data, creation time, propagation identifiers, and an optional error message. JSON-compatible mappings, lists/tuples, strings, booleans, integers, finite floats, and null are accepted. Opaque objects, non-string mapping keys, and non-finite floats are rejected; values are never silently converted with `str()` or `repr()`.

The built-in `retry_safe`, `fallback_default`, and `rebuild_context` recovery actions return JSON-compatible dictionaries. A custom backend used with persistent replay must follow the same result contract.

On replay, a completed stage is restored as a typed `RecoveryExecutionResult` using the current request ID and strategy request ID, while retaining the stored outcome and original propagation context. The recovery backend is not called again.

## Failure policy

Both successful and failed executions are persisted as completed outcomes. A failed execution is therefore replayed as the same failure and is not automatically retried under the same stage identity. A retry requires an explicit higher-level policy that changes or supersedes the stage identity; callers must not assume that claim-generation advancement retries a completed failure.

## Concurrency and fencing

`SQLiteReplayStageStore.begin` validates the parent claim's owner token and generation. A completed stage is returned to a newer valid generation. An unfinished claimed stage may be taken over only according to the store's generation rules. `complete` validates the same current owner/generation pair, preventing a stale executor from completing a stage after ownership has moved.

The boundary retains its existing in-process request de-duplication and event-bus execution path. Calls that do not supply replay metadata retain the legacy process-local behavior.

## Exactly-once limitation

This contract prevents re-execution after the stage completion record has been durably committed. It does **not** make arbitrary external recovery side effects exactly once. A process can terminate after the backend performs its side effect but before `SQLiteReplayStageStore.complete` commits. A later generation may then take over the claimed stage and invoke the backend again.

A backend that performs externally visible effects must therefore use its own stable idempotency key, or atomically commit the effect and the stage completion in the same transactional resource. The stage store alone cannot close that crash window.

## Verification

The P2-2 regression tests cover restart replay with a new owner/generation, persisted failure replay, distinct stage inputs, partial-metadata rejection, and legacy calls without replay metadata. Run the focused test file, full test suite, Ruff, and Mypy before considering the patch complete.
