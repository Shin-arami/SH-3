# Part 11-34 — Persistent Replay Expired-Claim Policy Gate

## Purpose

Part 11-33 added an opt-in strict gate for pending terminal-evidence reconciliation. The readiness report also identifies expired `claimed` leases, which can permit another worker to take ownership and increment the fencing generation. Maintenance and recovery pipelines need an explicit way to stop when expired claims exist without changing the existing default behavior.

## Changes

The `check` command accepts `--fail-on-expired-claims`.

- Without the option, the readiness check continues to report expired claims and return success when all integrity checks pass.
- With the option and no expired claims, the command prints `EXPIRED_CLAIM_GATE: PASS` and exits with code `0`.
- With the option and one or more expired claims, the command prints `EXPIRED_CLAIM_GATE: FAIL` to stderr and exits with code `3`.
- Integrity or configuration errors continue to use exit code `1`.
- If both strict policy gates fail, both failures are reported. The existing pending-reconciliation gate has precedence and the command returns exit code `2`; otherwise the expired-claim gate returns `3`.

The gate evaluates the existing `expired_claim_count`; it does not mutate leases, release claims, reconcile evidence, or determine whether a stale worker can still produce external effects.

## Safety boundary

This is an opt-in, read-only policy gate for the `check` command. Expiration indicates that the stored lease deadline has passed, not proof that a worker has been terminated. Operators should inspect worker state and side-effect fencing before recovery or replay. Do not clear expired claims with manual SQL updates.

## Tests

Tests cover unchanged default behavior, the distinct expired-claim exit code, passing when a lease remains active, and deterministic precedence when both the pending-evidence and expired-claim gates fail. Cycle and evidence identifiers remain redacted by default.
