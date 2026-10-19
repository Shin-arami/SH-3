# Part 11-55 - Persistent Replay Backup/Restore Partial Snapshot Cleanup Contract

## Purpose

Parts 11-52 and 11-54 cover timeout validation and same-source/destination rejection. This part verifies the shared snapshot lifecycle after a temporary snapshot has already been created: a snapshot-stage failure or a failed verification must not leave a `.partial` file, publish a destination, or mutate the source database.

## Contract

Fault-injection tests exercise both `backup` and `restore` across two failure points:

- The online snapshot operation fails after the temporary file is created.
- The snapshot operation returns, but verification rejects the temporary file as an invalid SQLite database.

For every case:

- The command reports exit code `1` and exactly one action-specific JSON error envelope.
- Standard error does not contain a traceback or the full source/destination paths.
- The source database remains byte-for-byte unchanged.
- The destination is not published.
- The temporary `.partial` snapshot is removed.

## Compatibility and safety

This part adds tests and documentation only. It does not change production code, command-line parsing, or the published JSON Schema. Failures are injected deterministically in-process by replacing the snapshot helper; no filesystem exhaustion or timing-sensitive race is required.

## Validation

Run `validate_patch.ps1`, then inspect the staged diff and run `git diff --cached --check` before committing. The validation script runs focused and related regression tests, Ruff, Mypy, JSON Schema syntax validation, the full pytest suite, and the deprecation-warning gate.
