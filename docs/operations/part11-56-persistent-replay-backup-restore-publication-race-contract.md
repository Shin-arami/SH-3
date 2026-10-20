# Part 11-56 - Persistent Replay Backup/Restore Publication-Race Contract

## Purpose

Parts 11-54 and 11-55 verify normalized source/destination identity rejection and cleanup after snapshot-stage or verification failures. This part covers the distinct race between destination preflight validation and final snapshot publication: another writer may create the destination after preflight but before the no-overwrite publication operation.

## Contract

Deterministic fault-injection tests exercise both `backup` and `restore` by making a competing destination appear immediately before the publication link operation.

- The operation exits with code `1` and emits exactly one action-specific JSON error envelope with `destination_exists` / `FileExistsError`.
- The JSON error envelope does not disclose the destination path; standard error reports the refusal without a traceback.
- The competing writer's destination content remains byte-for-byte unchanged.
- The source database remains byte-for-byte unchanged.
- The temporary `.partial` snapshot is removed after the publication attempt fails.

## Compatibility and safety

This part adds tests and documentation only. It does not alter production code, CLI parsing, the error envelope, or the published JSON Schema. The race is simulated deterministically in-process by replacing `os.link`; no concurrent process or timing-sensitive test is needed.

## Validation

Run `validate_patch.ps1`, then inspect the staged diff and run `git diff --cached --check` before committing. The validation script runs the focused contract, related Backup/Restore regressions, Ruff, Mypy, JSON Schema syntax validation, the full pytest suite, and the deprecation-warning gate.
