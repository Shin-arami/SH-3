# Part 11-46 窶・Persistent Replay JSON Policy-Gate Disclosure Invariance

## Purpose

Part 11-45 verifies that both redacted and explicitly disclosed pending-reconciliation reports satisfy the published JSON Schema v1 contract. This part verifies that opting into identifier details does not alter the policy-gate decision or any other JSON report field.

## Changes

A contract test invokes `check --json --fail-on-pending-reconciliation` on a synthetic pending terminal-evidence reconciliation, first with default redaction and then with `--include-pending-cycle-ids`.

- Both runs return exit code `2` and report the same failed pending-reconciliation gate and count.
- The default JSON omits `pending_reconciliations`; the opt-in JSON includes the expected cycle and evidence identifiers.
- Standard error is unchanged, every other JSON field is identical, and both reports satisfy the published schema.

## Compatibility and safety

This change adds a test and documentation only. It does not modify production code, the published schema, default identifier redaction, or policy-gate behavior. Synthetic identifiers are stored only in the temporary test database.

## Validation

Run `validate_patch.ps1`, then the full pytest suite and the Deprecation gate before committing.
