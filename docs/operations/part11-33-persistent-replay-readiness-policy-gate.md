# Part 11-33 — Persistent Replay Readiness Policy Gate

## Purpose

The read-only persistent replay check reports pending terminal evidence without treating every pending record as an integrity failure. That default is important because a check can overlap with a live worker's finalization window. Some deployment and maintenance workflows, however, need a strict policy that refuses to continue while any pending reconciliation is reported.

## Changes

The `check` command accepts `--fail-on-pending-reconciliation` as an explicit policy gate.

- Without the option, behavior remains unchanged: pending evidence is reported and the command succeeds when integrity and consistency checks pass.
- With the option and zero pending records, the command prints `PENDING_RECONCILIATION_GATE: PASS` and exits with code `0`.
- With the option and one or more pending records, the command prints `PENDING_RECONCILIATION_GATE: FAIL` to stderr and exits with code `2`.
- Other operational or integrity errors retain the existing error path and exit code `1`.

The gate does not reveal cycle IDs by default, even when it fails. To include details, operators must still explicitly pass `--include-pending-cycle-ids` and use an appropriately protected terminal/log context.

## Safety boundary

This policy gate is opt-in and read-only. It does not change or reconcile claim records. Since an unexpired pending claim may belong to a live worker, a strict gate may temporarily reject a healthy in-progress finalization window; operators should assess worker activity before taking recovery action. Do not clear the condition with manual SQL edits.

## Tests

Tests verify the default non-blocking behavior, a distinct non-zero exit code when the opt-in gate detects pending evidence, redaction of cycle/evidence identifiers in that failure path, and success when no pending evidence exists.
