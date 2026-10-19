# Part 11-49 窶・Persistent Replay JSON Error-Report Disclosure Invariance

## Purpose

Parts 11-44 through 11-48 establish identifier redaction and disclosure invariance for successful JSON reports and policy-gate failures in the CLI process. This part covers the readiness-error branch, where normal report details must not be emitted at all.

## Changes

A process-level contract test creates an intentionally incomplete persistent-replay database containing synthetic terminal evidence but no replay-claim table, then invokes `check --json` with and without `--include-pending-cycle-ids`.

- Both processes return exit code `1` with the same `readiness_check_failed` JSON error envelope.
- The error envelope contains no pending reconciliation details or identifiers.
- Standard output and standard error are identical between default redaction and explicit identifier opt-in.
- The JSON report does not expose the database path, cycle identifier, or evidence identifier.

## Compatibility and safety

This part adds a process-level contract test and documentation only. It does not change production code, the published JSON Schema, readiness error classification, or disclosure defaults. Test data resides in a temporary database.

## Validation

Run `validate_patch.ps1`, then the full pytest suite and the Deprecation gate before committing.
