# Part 11-48 — Persistent Replay JSON Expired-Claim Gate Process Disclosure Invariance

## Purpose

Part 11-47 verifies identifier-disclosure invariance across the real CLI process when both policy gates fail, confirming pending-reconciliation exit-code precedence. This part isolates the expired-claim gate so the process-level contract also covers its distinct exit code `3`.

## Changes

The process contract test creates a synthetic expired claim with canonical terminal evidence and runs `check --json --fail-on-expired-claims` with default redaction and with `--include-pending-cycle-ids`.

- Both processes return exit code `3`; the pending-reconciliation gate is not enabled, so it does not appear as a failed gate.
- Both JSON reports retain `expired_claims=1`, `pending_evidence_reconciliation=1`, and `policy_gates={"expired_claims":"fail"}`.
- Standard error is identical and contains no cycle or evidence identifiers.
- Default stdout redacts identifiers; explicit opt-in includes the reconciliation detail, and all other JSON fields are identical.

## Compatibility and safety

This part adds a process-level contract test and documentation only. It does not modify production code, the published JSON Schema, default identifier redaction, or policy-gate behavior. All test data remains in a temporary database.

## Validation

Run `validate_patch.ps1`, then the full pytest suite and the Deprecation gate before committing.
