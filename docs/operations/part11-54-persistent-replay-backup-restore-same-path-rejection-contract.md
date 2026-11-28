# Part 11-54 - Persistent Replay Backup/Restore Same-Path Rejection Contract

## Purpose

Parts 11-52 and 11-53 cover timeout validation and the command scope of the pending-identifier disclosure flag. This part closes a separate backup/restore safety gap: the command must reject a destination that resolves to its input database, including a lexical path alias containing `..`.

## Contract

Process-level tests exercise both `backup` and `restore` with JSON output enabled.

- The operation exits with code `1` and emits exactly one JSON error object.
- The JSON error identifies the command and the stable `readiness_check_failed` / `PersistentReplayReadinessError` category.
- Standard error reports the same-path rejection without disclosing the source path or a traceback.
- The input database remains present and byte-for-byte unchanged.
- No `.partial` snapshot file is left behind because same-path validation occurs before temporary snapshot creation.

## Compatibility and safety

This part adds tests and documentation only. It does not modify production code, the CLI parser, or the published JSON Schema. Test databases and alias paths are isolated under pytest's temporary directory.

## Validation

Run `validate_patch.ps1`, then inspect the staged diff and run `git diff --cached --check` before committing. The validation script runs the focused test, Ruff, Mypy, JSON Schema syntax validation, the full pytest suite, and the deprecation-warning gate.
