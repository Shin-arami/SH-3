# Part 11-64 - Persistent Replay Snapshot Cleanup Continuation Contract

## Purpose

Part 11-63 guarantees the source connection is still closed when closing the destination connection fails. This part covers the analogous temporary snapshot lifecycle: a failure removing one SQLite sidecar must not prevent attempts to remove the remaining sidecars and the temporary main database file.

## Contract

Deterministic tests exercise both `backup` and `restore` with two injected failures: the primary snapshot operation raises a readiness error, and removal of the temporary `-wal` sidecar raises an `OSError`.

- Every cleanup target (`-wal`, `-shm`, `-journal`, then the temporary main file) receives an unlink attempt, even if an earlier attempt raises.
- The primary snapshot error remains the propagated error and records a note describing cleanup failure(s), rather than being masked by the cleanup exception.
- The source database remains byte-for-byte unchanged.
- The destination is not published and temporary main/sidecar paths are not left behind when subsequent cleanup operations succeed.
- CLI arguments and the published JSON Schema remain unchanged.

## Implementation

The cleanup block collects `OSError` instances and continues across all targets. If cleanup fails while another exception is already being propagated, it adds a concise exception note to the primary exception. If cleanup fails after an otherwise successful operation, it raises the first cleanup error after all cleanup targets have been attempted. It does not attempt a path-based rollback of a published destination.

## Validation

Run `validate_patch.ps1`, inspect production/test/documentation changes, and run `git diff --cached --check` before committing. The script covers the new cleanup continuation contract, related Backup/Restore safety contracts, Ruff, Mypy, published JSON Schema syntax, the full pytest suite, and the deprecation-warning gate.
