# Part 11-128 — Temporary Allocation Failure After Destination Parent Creation

## Scope

This contract covers backup and restore when the destination parent directory is created successfully, but `tempfile.mkstemp` fails before any SQLite snapshot is opened or copied.

## Required behavior

- Preserve the original allocation `PermissionError` as the raised exception.
- Do not start online backup or attempt destination publication.
- Keep the newly created parent directory; do not remove a directory that the operation created as a preparatory step.
- Leave the requested destination absent and create no `.partial` snapshot artifacts.
- Do not modify the source database or its pre-existing SQLite sidecars.
- After the injected allocation failure is removed, permit a retry to a new destination within the existing parent.
- Apply equally to `backup_database` and `restore_database`.

## Implementation boundary

This is a test-and-operations-documentation-only contract. Production code, CLI behavior, and the published persistent-replay JSON Schema are unchanged.

## Validation

Run `validate_patch.ps1` from the repository root with the Python 3.12+ environment selected. The script runs the focused contract, related snapshot/publication/cleanup/recovery regressions, Ruff, Mypy, JSON Schema syntax, full pytest, the deprecation-warning gate, whitespace validation, and `git diff --check`.
