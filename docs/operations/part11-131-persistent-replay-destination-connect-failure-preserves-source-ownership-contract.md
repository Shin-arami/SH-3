# Part 11-131 — Destination connection open failure preserves source ownership

## Contract

If SQLite cannot open the temporary destination connection for an online snapshot, the destination-open `sqlite3.Error` remains the cause of the operational readiness error. The online backup itself must not run.

The source connection has two ownership modes:

- **Owned source:** the snapshot helper opened it, so it must attempt to close it even when destination connection creation fails. A source-close failure is attached as a diagnostic note and must not replace the destination-open failure.
- **Borrowed source:** the caller supplied it, so the snapshot helper must not close it. The caller retains ownership when destination connection creation fails.

In either case, no temporary snapshot is published or left on disk.

## Scope

The contract test injects the destination connection-open failure and, for the owned-source case, a source-close failure. It checks the preserved cause, the ownership-specific close behavior, the lack of backup invocation, and absence of a temporary snapshot.

Production code, CLI output contracts, and the published JSON Schema are unchanged by this part.

## Validation

Run `validate_patch.ps1` from the repository root with the SH-3 Python 3.12+ interpreter. The script runs the focused contract, related snapshot/publication/cleanup/recovery tests, Ruff, Mypy, JSON Schema syntax parsing, full pytest, the DeprecationWarning gate, whitespace checks, and `git diff --check`.
