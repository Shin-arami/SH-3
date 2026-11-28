# Part 11-39 — Persistent Replay JSON Policy Exit-Code Invariants

## Purpose

Part 11-38 publishes JSON Schema v1 for persistent replay operation reports. The schema describes individual field types and allowed values, but field-level checks alone must not permit contradictory combinations of `policy_gates` and `exit_code`.

## Contract additions

The success envelope now constrains policy-gate state and exit code together:

- Exit code `0`: every gate that is present must be `pass`.
- Exit code `2`: `pending_reconciliation` must be `fail`. This gate retains precedence when both gates fail.
- Exit code `3`: `expired_claims` must be `fail`, and `pending_reconciliation` must not be `fail`.
- Gate keys remain optional because callers opt in to each gate independently.
- Error envelopes remain exit code `1`; the rules do not change text output, JSON shape, or CLI behavior.

The contract uses JSON Schema Draft 2020-12 conditional keywords. The test-only schema validator is extended to evaluate `allOf`, `if`/`then`/`else`, and `not` so contract tests exercise those constraints without introducing a runtime or development dependency.

## Safety and compatibility

No production Python code or output fields are changed. This tightens the published v1 schema to reject contradictory reports; reports currently emitted by SH-3 should already satisfy the rules. Consumer code should continue to branch on the process exit code as well as inspect the JSON report.

## Tests

Tests check valid no-gate and gate combinations, both-gates-fail precedence, and rejection of contradictory combinations such as exit code `0` with a failed gate, exit code `2` without a pending-reconciliation failure, or exit code `3` when the pending-reconciliation gate failed.
