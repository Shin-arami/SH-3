# Part 11-122 — Publication Collision Preserves Distinct Competing Content

## Contract

When a competing publisher creates the requested destination after snapshot creation has begun, the losing backup/restore operation must not replace or damage the destination. The protected destination in this contract is an independently initialized, valid SQLite database with a different evidence count from the source snapshot. This makes content preservation observable rather than merely comparing two links to an equivalent source copy.

The injected publication race links the independently populated winner to the destination and raises `FileExistsError`. Simultaneously, cleanup of one temporary WAL sidecar and the temporary `.partial` snapshot fails. The original collision exception must remain primary and retain the cleanup diagnostics as a note.

## Assertions

- Backup and restore paths preserve the competing publisher's distinct database at the destination.
- The destination remains a hard link to the winner and its bytes remain unchanged.
- The cleanup loop attempts all sidecar and temporary-snapshot removals even after two injected failures.
- The raised `FileExistsError` remains the primary exception and has no replacement cause; cleanup failures appear in its diagnostic note.
- After explicitly removing only the injected temporary artifacts, a new-destination retry succeeds and contains the source's original counts and index definition.
- The winning database and its sidecars are unchanged throughout the losing operation and retry.

## Scope

This is a test-and-operations-document-only contract. Production code, CLI behavior, and the published persistent-replay JSON Schema are unchanged.

## Validation

Run `validate_patch.ps1` from the SH-3 repository root with `SH3_PYTHON` pointing to Python 3.12 or newer. The validator executes the focused test, related regressions, Ruff, Mypy, JSON Schema parsing, the full pytest suite, the deprecation-warning gate, whitespace checks, and `git diff --check`.
