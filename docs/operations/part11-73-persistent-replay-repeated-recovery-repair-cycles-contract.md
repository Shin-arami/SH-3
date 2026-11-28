# Part 11-73 - Persistent Replay Repeated Recovery and Repair Cycles Contract

## Purpose

Part 11-72 verifies that a required-index failure recurs predictably after explicit repair. This part extends that check across three complete fault/repair cycles to ensure the same diagnostics and report state remain consistent over repeated operations.

## Contract

The contract runs for backup-destination and restore-destination scenarios. In each of three cycles it removes the required `sh3_replay_claims_state_idx` index, runs `check --json`, explicitly recreates the index, and then runs `check --json` again. It verifies that:

- every missing-index check returns the same sanitized JSON error envelope and the same path-redacted diagnostic;
- every explicitly repaired check returns a successful JSON readiness report, and all successful reports are identical across cycles;
- the check command never repairs the missing index by itself;
- source and destination database bytes remain unchanged during each check (the test's explicit index drop/create operations are separate fault injection and repair steps);
- synthetic `.partial`, `.partial-wal`, `.partial-shm`, and `.partial-journal` artifacts remain present with byte-for-byte identical contents through all cycles;
- the exact residual-artifact filename set is unchanged throughout the test.

## Compatibility and safety

This part adds only a contract test and operations documentation. Production code, CLI arguments, JSON report fields, and the published JSON Schema are unchanged. All database mutations occur in pytest's temporary directory and are limited to explicit index fault injection and repair.

## Operator recovery

If repeated checks alternate between failure and success because required schema elements are being changed, treat each failed report as authoritative for the database state at that moment. The checker remains read-only and must not be treated as a repair tool. Preserve residual snapshot artifacts until the database's current state has been independently verified and a separate cleanup decision is recorded.

## Validation

Run `validate_patch.ps1` from the SH-3 repository root with Python 3.12+. It runs this contract, related recovery and JSON CLI regressions, Ruff, Mypy, published JSON Schema syntax validation, the full pytest suite, the deprecation-warning gate, whitespace checks, and `git diff --check`.
