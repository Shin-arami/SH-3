# P3-1C - Idempotency Collision and Recovery Propagation Hardening

## Scope

P3-1C hardens P3-1A recovery backend key propagation and P3-1B optimizer
Action/rollback key propagation. It does not add a durable Action result store.

## Optimizer parent-key scope

A keyed `OptimizationUpdateRequest` is scoped by both the supplied parent key
and `tenant_id`. Within one `OptimizationUpdateBoundary` instance, the boundary
records a fingerprint of `optimization_id`, the ordered Action list, and the
tenant. Reuse of the same tenant-scoped key with different fingerprint input
is rejected with `ValueError`; an identical input returns the in-memory result.

This fingerprint registry is process-local. It protects retries and duplicate
requests while that boundary instance is alive, but it is not a durable,
cross-restart idempotency ledger. Persistent replay remains governed by the
existing Replay Stage Store input fingerprint and downstream Action/backend
deduplication obligations. When `tenant_id` is absent, requests share the
unscoped `None` tenant namespace and callers must supply globally unique keys
within that namespace.

Trace, causation, and correlation identifiers are intentionally excluded from
the semantic fingerprint because replay can carry new event lineage while
representing the same optimizer operation.

## Rollback uncertainty

If a rollback callback fails after an Action result indicates a change, the
`OptimizationActionResult` and normalized `OptimizationUpdate` carry
`state_uncertain=true`. A non-mapping or ambiguous Action result is
conservatively treated as uncertain; an explicit `{"changed": false}` result
is not. The update boundary does not emit a normal `ContextUpdated`,
`PolicyUpdated`, or `MemoryUpdated` event for a failed update. Instead,
`OptimizationUpdateFailed` includes `state_uncertain=true` and the serialized
per-Action result retains the uncertainty marker.

An uncertain state requires downstream reconciliation or operator review.
It must not be interpreted as a successful compensation.

## Context rebuild key propagation

`SelfHealingCore` forwards `idempotency_key` to a context manager's `clear`
method when that callable exposes a keyword parameter named
`idempotency_key` or accepts `**kwargs`. Legacy `clear()` methods remain
supported and are invoked without arguments when they do not expose the key.
The built-in `runtime.ContextManager.clear` accepts the optional keyword,
validates nonblank values, and remains repeatable because it clears the
in-memory stack. A custom manager that performs non-idempotent external work
must durably deduplicate that work using the supplied key; a legacy manager
that cannot accept the key does not gain that guarantee.

## Exactly-once boundary

P3-1C does not atomically couple the Replay Stage Store with arbitrary external
systems, and it does not persist optimizer Action/rollback results. Key
propagation, process-local collision detection, and state-uncertainty reporting
are not by themselves proof of exactly-once external effects. Custom backends,
Actions, rollback callbacks, and custom context managers remain responsible for
durable key/outcome recording at the system that owns each side effect.

## Validation

Focused tests:

```powershell
& $Python -m pytest -q `
    tests\kernel\test_optimizer_update_boundary.py `
    tests\kernel\test_recovery_execution_boundary.py `
    tests\runtime\test_context_manager.py
```

Then run the full suite, Ruff, Mypy, and `git diff --check` using the project's
normal validation commands. This patch does not stage, commit, or push files.
