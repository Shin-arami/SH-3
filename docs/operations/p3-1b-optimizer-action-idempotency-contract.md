# P3-1B - Optimizer Action Idempotency Contract

## Purpose

P3-1B narrows the optimizer idempotency scope from a single parent request to each action and its compensating rollback. The parent key is supplied by the learning optimizer/update boundary. `SystemOptimizer` derives a deterministic child key for each action using the parent key, action name, and zero-based action ordinal.

## Action contract

When a parent key is present, each `OptimizationAction.apply` callback receives:

- `context["idempotency_key"]`: the deterministic key for this action invocation.
- `context["parent_idempotency_key"]`: the parent learning/update-stage key.

The generated child key is also exposed on `OptimizationActionResult` and `OptimizationUpdate`. Results include key fields in their serialized representation only when a key is present, preserving the previous no-key payload shape.

## Rollback contract

A rollback for a keyed action receives a separately derived key through the keyword argument `idempotency_key`. A keyed rollback callback must accept that keyword explicitly or through `**kwargs`. A callback that cannot accept it is not invoked; the rollback result is reported as failed. This is a fail-closed compatibility rule for keyed execution.

In legacy no-key execution, rollback callbacks continue to receive their original single positional result argument. Built-in rollback callbacks accept the new keyword but do not themselves provide durable deduplication.

If an action sequence fails, `execute_actions` replaces each rolled-back entry in its returned tuple with the actual rollback result. This makes the returned execution data distinguish a completed action from a successfully compensated action or a failed compensation.

## Event and boundary propagation

`OptimizationUpdateBoundary` preserves action, parent, and rollback keys while normalizing results. `ContextUpdated`, `PolicyUpdated`, and `MemoryUpdated` event payloads include the key fields when present. The parent key remains on the update request and the child key identifies the individual action.

## Durability and exactly-once limits

This patch defines key derivation and propagation; it does **not** add a durable per-action result store or an atomic transaction spanning action side effects and rollback completion. Passing a key does not, by itself, guarantee exactly-once execution.

Custom actions and rollback callbacks that perform non-idempotent external effects must durably record the key and outcome, return the same logical result for repeated use of the same key, and reject reuse of a key with conflicting input. The downstream system must own that deduplication guarantee. In-memory built-in context/policy mutations are not promoted to durable exactly-once effects by this patch.

## Validation

Run the focused tests:

```powershell
& $Python -m pytest -q `
  tests\kernel\test_system_optimizer.py `
  tests\kernel\test_optimizer_update_boundary.py `
  tests\integration\test_p1_5_optimizer_action_execution.py
```

Then run the full suite and static checks according to the repository's normal validation procedure. The patch does not stage, commit, or push files.