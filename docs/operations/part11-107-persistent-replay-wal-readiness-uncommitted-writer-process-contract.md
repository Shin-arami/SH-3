# Part 11-107 — WAL Readiness Under an Uncommitted Writer Process

## Contract

The readiness API and the JSON CLI must remain observational while a separate writer holds a WAL-mode write transaction with uncommitted schema and `user_version` changes. Repeated readiness operations must not commit writer work, checkpoint the WAL, repair schema, or alter the main database/WAL byte images.

## Covered behavior

- Run the contract for both backup-created and restore-created destinations.
- Pin a committed read snapshot before a writer opens `BEGIN IMMEDIATE`.
- Stage a probe index and a `user_version` marker without committing.
- Attempt creation of the required index three times inside savepoints; each attempt must fail with the same `already exists` error and preserve the outer writer transaction.
- Run the readiness API three times and the JSON CLI in separate Python processes three times while the writer transaction remains open. Each result must match the committed readiness report; the main database and WAL bytes must remain unchanged.
- Commit the writer only after all read-only checks finish; the old reader must retain its prior snapshot until it is rolled back, while a new observer sees the committed marker and probe index.
- Run the process-isolated JSON check twice after commit and verify stable output and unchanged database/WAL images.
- Preserve source and backup bytes, residual `.partial`/sidecar artifact bytes, and the canonical required index definition.

## Scope

This is a test-and-documentation-only contract. It does not change production code, CLI behavior, or the published JSON Schema.

## Validation

Run `validate_patch.ps1` from the repository root with `SH3_PYTHON` set to the Python 3.12+ interpreter. The script executes the focused contract, related WAL/index/recovery/CLI tests, Ruff, Mypy, JSON Schema syntax validation, the full pytest suite, the deprecation-warning gate, whitespace validation, and `git diff --check`.
