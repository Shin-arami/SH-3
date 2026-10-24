# Part 11-121 — Publication Collision Error Preserved Through Cleanup Failure Contract

## Purpose

Verify the distinct `FileExistsError` publication-race path when temporary snapshot cleanup also fails. A concurrent publisher's already-created destination must remain untouched, and cleanup diagnostics must not replace the collision error.

## Contract

- Cover both backup-destination and restore-destination operations.
- Simulate a concurrent publisher by hard-linking a verified winner snapshot to the requested destination immediately before raising `FileExistsError`.
- Inject failures for temporary WAL-sidecar and `.partial` cleanup, while proving every cleanup item is still attempted.
- Verify the raised exception remains `FileExistsError` with the no-overwrite message; cleanup diagnostics are attached as notes and report two failed artifacts.
- Verify the destination remains the same hard link and byte-identical to the winning snapshot; do not inspect it through SQLite while asserting the race because WAL inspection may create alias sidecars.
- Remove only injected orphan artifacts and prove a retry to a separate destination succeeds without changing the concurrent winner.

## Scope

Test and operations documentation only. No production implementation, CLI output, or published JSON Schema changes. The contract isolates collision-specific exception precedence from the generic publication `OSError` boundary exercised by Part 11-120.

## Validation

Run `validate_patch.ps1` using the Python 3.12+ interpreter selected by `SH3_PYTHON`. The gate includes focused and related tests, Ruff, Mypy, published JSON Schema syntax, the full pytest suite, the deprecation-warning gate, whitespace validation, and `git diff --check`.
