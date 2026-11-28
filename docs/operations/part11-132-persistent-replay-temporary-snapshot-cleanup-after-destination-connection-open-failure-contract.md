# Part 11-132 — Temporary Snapshot Cleanup After Destination Connection Open Failure

## Contract

If SQLite cannot open the temporary snapshot destination after `mkstemp` has allocated the `.partial` file, the failure must remain the primary exception and the outer snapshot operation must clean up the allocated temporary path. The requested destination must not be published, protected source/backup database artifacts must remain unchanged, and a retry after the injected failure is removed must succeed.

The contract is exercised for both `backup_database` and `restore_database`. The test injects `sqlite3.OperationalError` only for the temporary destination `Path` and delegates all other SQLite connections to the original function. It asserts the temporary file exists at the failing connection boundary, is removed afterward, and does not leave sidecars or destination artifacts.

## Scope

- Test and operations documentation only.
- No production, CLI, or published JSON Schema changes.
- Run `validate_patch.ps1` with the SH-3 Python 3.12+ environment to check focused tests, related regressions, Ruff, Mypy, schema syntax, the full suite, the deprecation-warning gate, whitespace, and `git diff --check`.
