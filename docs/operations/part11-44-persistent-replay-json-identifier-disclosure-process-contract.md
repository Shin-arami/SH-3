# Part 11-44 — Persistent Replay JSON Identifier Disclosure Process Contract

## Purpose

Part 11-41 established the JSON contract at the CLI process boundary, including default redaction during policy-gate failures. This part covers the separate opt-in path for pending reconciliation details, where cycle and evidence identifiers are intentionally emitted only when an operator supplies `--include-pending-cycle-ids`.

## Changes

Adds subprocess tests for `python -m infrastructure.security.persistent_replay_ops check` using a temporary SQLite database with canonical terminal evidence beside a non-completed claim.

- Without `--include-pending-cycle-ids`, the process returns one JSON object and does not disclose the cycle or evidence identifier in stdout or stderr.
- With `--include-pending-cycle-ids`, the JSON report contains one `pending_reconciliations` detail with the established field names, claim state, generation, attempt count, lease status, and canonical evidence identifier.
- Both paths assert process exit code `0`, empty stderr, and a single JSON line on stdout.

## Compatibility and safety

This part adds tests and documentation only. It does not modify runtime code, the published JSON Schema, default redaction behavior, or exit-code semantics. Identifier disclosure remains an explicit opt-in because cycle and evidence identifiers may reveal application context. Operators should avoid enabling detailed output in broadly shared logs unless that exposure is acceptable.

## Validation

Run the focused subprocess test, Ruff, and Mypy as provided by the patch validation script. Before committing, run the full pytest suite and the Deprecation gate.
