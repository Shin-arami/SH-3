# Part 11-35 — Persistent Replay JSON Readiness Report

## Purpose

Part 11-33 and Part 11-34 introduced optional fail-closed gates for pending evidence reconciliation and expired replay leases. Automation needs a stable machine-readable report so it can consume the counts, selected gate results, and exit code without parsing human-oriented output.

## Changes

The `check` subcommand accepts `--json`. On a successful storage integrity/consistency inspection, it writes one JSON object to stdout with `schema_version`, the check summary, `policy_gates`, and `exit_code`.

- The option is opt-in; the existing text output remains the default.
- `policy_gates` includes only gates explicitly enabled for the invocation. Values are `pass` or `fail`.
- The `exit_code` field matches the command exit code. Pending-reconciliation failure remains code `2`; expired-claim failure remains code `3` unless the pending-reconciliation gate also fails, in which case code `2` retains precedence.
- The report identifies a successful integrity/consistency inspection with `integrity_status: "pass"`; policy-gate outcomes are reported separately and may still cause a non-zero command exit.
- Cycle and evidence identifiers are omitted by default. They appear in `pending_reconciliations` only when `--include-pending-cycle-ids` is explicitly supplied.
- Database/inspection errors retain the existing error path: a diagnostic is written to stderr, the command returns `1`, and no successful JSON report is emitted.

Example:

```powershell
py -3.12 -m infrastructure.security.persistent_replay_ops check `
    --database .\state\replay.sqlite3 `
    --fail-on-pending-reconciliation `
    --fail-on-expired-claims `
    --json
```

## Safety boundary

The report is read-only. It does not reconcile evidence, release leases, repair records, or imply that an expired lease's former worker has stopped. Treat the output as an operational observation, not a recovery command. Do not enable identifier details in shared logs without reviewing their sensitivity.

## Tests

Tests cover JSON parsing, stable summary fields, default identifier redaction, explicit detail opt-in, individual gate status reporting, combined-gate precedence, and the active-lease passing case. Existing text output remains the default path.
