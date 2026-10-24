# Part 11-127 — Destination Parent Creation Failure: No Snapshot Allocation

## Contract

`backup_database` and `restore_database` must fail closed if the destination parent directory cannot be created. The original `PermissionError` from parent creation remains the reported exception. Since parent preparation occurs before snapshot allocation, this failure must not allocate a `.partial` snapshot, start an online backup, or attempt publication.

## Required invariants

- The destination-parent creation attempt is observed exactly once and its injected `PermissionError` instance is preserved.
- `tempfile.mkstemp`, `_backup_to_temporary`, and `os.link` are not called after parent creation fails.
- The missing destination parent and destination remain absent after failure.
- No partial snapshot artifact appears under the test's temporary root.
- Source and (for restore) backup database files and SQLite sidecars retain their captured bytes/existence state.
- After the injected filesystem fault is removed, a retry to a sibling destination creates the parent and publishes a snapshot with matching readiness counts.

## Scope

This is a contract-test and operations-document change only. It does not modify production code, CLI behavior, or the published JSON Schema.

## Validation

Run the Part 11-127 validator from the SH-3 repository root with the project's Python 3.12+ interpreter. The validation script runs the focused contract, related snapshot/publication/cleanup regressions, Ruff, Mypy, JSON Schema syntax parsing, the full pytest suite, the deprecation-warning gate, whitespace validation, and `git diff --check`.
