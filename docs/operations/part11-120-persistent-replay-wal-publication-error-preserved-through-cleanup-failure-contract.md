# Part 11-120 — WAL Snapshot Publication Error Preserved Through Cleanup Failure Contract

## Purpose

Verify the exception-priority boundary when snapshot publication fails and temporary cleanup also encounters multiple failures. The original publication error must remain the raised `PersistentReplayReadinessError`; cleanup failures must be attached as diagnostic notes rather than replacing the primary error.

## Contract

- Cover both backup-destination and restore-destination operations.
- Inject a publication `OSError` and two cleanup `PermissionError` failures (temporary WAL sidecar and `.partial` snapshot).
- Verify the wrapped publication exception and its original cause remain primary.
- Verify the cleanup note reports `2 item(s)`, retains recovery guidance, and the cleanup loop attempts every planned artifact.
- Verify no destination is published, failed temporary artifacts remain inspectable, and protected source/backup database bytes are unchanged.
- Remove only the injected orphan artifacts and confirm retry succeeds to a separate destination without altering the failed target.

## Scope

Test and operations documentation only. No production implementation, CLI output, or published JSON Schema changes. The test protects exception precedence and recovery diagnostics around the existing `finally`-based cleanup behavior.

## Validation

Run `validate_patch.ps1` using the Python 3.12+ interpreter selected by `SH3_PYTHON`. The gate includes focused and related tests, Ruff, Mypy, published JSON Schema syntax, the full pytest suite, the deprecation-warning gate, whitespace validation, and `git diff --check`.
