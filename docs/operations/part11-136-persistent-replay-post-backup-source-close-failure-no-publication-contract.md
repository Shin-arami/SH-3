# Part 11-136 — Post-backup source/destination connection close failure and publication contract

## Contract

For both backup and restore, inject a destination SQLite connection whose `close()` closes the underlying connection and then raises `sqlite3.OperationalError`. The destination connection is only created after the online backup call returns; the test also inspects the snapshot schema and claim count inside `close()` to verify that the copy completed before the injected close failure.

The operation must propagate that close failure, remove the allocated `.partial` file and its sidecars, leave the publication destination absent, and preserve the source database (and the restore input backup). Once the injection is removed, retrying the same destination must succeed and preserve the expected replay-claim count.

## Scope

This part adds a contract test and this operations note only. It does not change production code, CLI output, or the published JSON Schema.

## Validation

Run `validate_patch.ps1` from the repository root with the SH-3 Python 3.12 environment selected through `SH3_PYTHON`. The validator runs the focused contract, related lifecycle regressions, Ruff, Mypy, JSON Schema parsing, the full pytest suite, the deprecation-warning gate, whitespace checks, and `git diff --check`.
