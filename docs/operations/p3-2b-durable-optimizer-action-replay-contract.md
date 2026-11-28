# P3-2B - Durable Optimizer Action and Rollback Replay Contract

## Scope

P3-2B connects the P3-2A `SQLiteReplayOperationStore` to the persistent
optimizer path. Each keyed Optimizer Action and its compensating Rollback have
independent durable operation rows. The parent Replay Claim and optimizer
Replay Stage remain the authorities for ownership and generation fencing.

The P3-2B integration is enabled only when the persistent runtime supplies an
operation store. Legacy in-memory `SH3Kernel()` construction and no-key Action
execution retain their previous path.

## Replay execution context

`ReplayExecutionContext` is an in-process-only value containing:

- replay `cycle_id` and `cycle_fingerprint`;
- parent optimizer `ReplayStageKey`;
- active owner token and generation;
- current tenant scope.

`LearningOptimizerBoundary` creates this scope from the claimed optimizer
Stage and the current event tenant. `SystemOptimizer` stores it in thread-local
state for the synchronous Action call chain. The owner token is not placed in
an event payload or serialized result. `OptimizationUpdateBoundary` dispatches
persistent-scope requests directly so its event handler cannot swallow a
ledger persistence exception or lose the private owner context.

A `DurableOperationPersistenceError` propagates through both optimizer
boundaries. It must not be converted into an ordinary optimizer failure: doing
so could mark the parent Stage completed while an Action or Rollback row is
still claimed.

## Immutable Action plan manifest

P3-2B adds `sh3_replay_operation_plans` to the same SQLite database. Its
composite identity is `(tenant_scope, parent_stage_key)`. It stores the
ordered Action names, plan version, SHA-256 integrity value, parent cycle, and
last active owner/generation.

The first plan for a parent optimizer Stage is immutable. On retry, the stored
plan is returned even if a restarted Runtime proposes a different list because
its in-memory snapshot has changed. The manifest is saved before an Action is
invoked. A changed plan version, malformed/corrupt manifest, or missing Action
registration fails closed before execution.
The manifest is additive and is included in existing SQLite online
backup/restore snapshots. Readiness validates its schema, parent references,
row identity, ownership generation, canonical JSON, and integrity digest.

## Action and Rollback outcomes

For every keyed Action:

1. The deterministic P3-1 child key and semantic input fingerprint form a
   tenant-scoped `ReplayOperationKey`.
2. The ledger claim is obtained under `BEGIN IMMEDIATE` after validating the
   active Replay Claim and parent Stage owner/generation.
3. A completed operation returns its integrity-verified result without
   re-invoking the callback.
4. Both successful and failed callback outcomes are stored as completed
   envelopes. A callback exception is conservatively recorded with
   `state_uncertain=true`, because the callback may have partially changed
   state before raising.
5. A failed ledger write propagates as `DurableOperationPersistenceError` and
   prevents parent Stage finalization.

Rollback has a separate P3-1-derived key and a separate ledger row. The store
requires the parent Action row to be completed in the same tenant, cycle,
parent Stage, action name, and ordinal. Successful and failed compensation
outcomes are persisted. Failed compensation retains the P3-1
`state_uncertain` calculation and is never represented as successful
compensation.

A process-local result cache preserves the original Python callback result
when the callback returned but the SQLite completion write failed. On a retry
inside the same `SystemOptimizer` instance, the cache is committed without
calling the callback again.

## Runtime-state replay policy

`OptimizationAction.replay_policy` defines whether a completed Action result
can safely cross a Runtime restart:

- `REQUIRE_LOCAL_STATE` is the default. For a completed result whose `changed`
  value is true or unknown, a new Runtime does not rerun the Action and does not
  claim that its old in-memory ContextManager/Policy state has been restored.
  It returns a failed result with `state_uncertain=true`, requiring
  reconciliation. An explicit `changed=false` result can be reused because it
  declares that no local mutation occurred.
- `REUSE_RESULT` permits a completed JSON-compatible result to be reused in a
  new Runtime. The callback must be a read-only/deterministic operation or
  otherwise have a durable deduplication guarantee. The built-in
  `compress_memory` Action uses this policy because it creates a derived view
  without mutating MemoryCore.

If an unfinished operation is taken over by a newer generation and no
same-process result is available, `REQUIRE_LOCAL_STATE` fails closed rather
than blindly repeating a possibly completed in-memory mutation. The uncertain
outcome is stored. `REUSE_RESULT` may invoke an unfinished callback again with
the same idempotency key; callbacks with external effects must deduplicate that
key at the system that owns the side effect.

## Exactly-once boundary

The ledger durably records Action and Rollback outcomes, and completed local
callbacks are not repeated once their outcome is committed. It cannot
atomically commit arbitrary external effects and the SQLite row. A crash after
an external effect but before `complete()` can cause a retry to invoke the
callback again. The downstream system must own durable deduplication of the
same stable key and reject conflicting input. P3-2B does not claim universal
exactly-once external effects.

The Action plan manifest stabilizes which Actions are attempted; it does not
persist the Runtime, ContextManager, PolicyEngine, or MemoryCore state itself.

## Validation

P3-2B tests cover:

- Action result reuse after a parent Stage finalization interruption in the
  same Runtime, without a second callback invocation;
- immutable plan reuse after restart when the new Runtime's snapshot proposes
  a different Action list;
- fail-closed handling of a completed stateful Action after Runtime restart;
- durable Action failure and failed Rollback outcomes, including
  `state_uncertain`, without repeated callbacks;
- explicit `REUSE_RESULT` behavior for a result-only Action after restart;
- Action-plan readiness and backup/restore preservation;
- fail-closed handling when a previously planned Action is no longer registered.

Run:

```powershell
& $Python -m pytest -q tests\kernel\test_persistent_optimizer_action_ledger.py
& $Python -m ruff check infrastructure kernel tests
& $Python -m mypy infrastructure\security\persistent_operation_store.py infrastructure\security\persistent_replay_ops.py infrastructure\security\persistent_replay_runtime.py kernel\replay_execution_context.py kernel\system_optimizer.py kernel\learning_optimizer_boundary.py kernel\optimizer_update_boundary.py
& $Python -m pytest -q
 git diff --check
```

P3-2B does not stage, commit, or push files.
