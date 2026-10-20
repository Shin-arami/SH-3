# Part 11-58 - Persistent Replay Backup/Restore WAL Snapshot Consistency and Cleanup Contract

## Purpose

Parts 11-54 through 11-57 cover path identity, partial-file cleanup after injected failures, atomic publication races, and invalid-source preflight. This part verifies a different valid-source boundary: committed records that remain in a SQLite write-ahead log (WAL) must be included in an online backup or restore even when the main database file has not yet been checkpointed. It also closes the temporary sidecar cleanup gap exposed by exercising WAL-mode snapshots.

## Contract

Process-level tests exercise both `backup` and `restore` while an anchor connection keeps the source database in WAL mode. A record is committed through the evidence store while the anchor remains open and automatic checkpointing is disabled on the anchor.

- The source has a non-empty WAL sidecar while its main database file remains byte-for-byte unchanged after the committed write.
- Both commands succeed and emit exactly one JSON success report containing the committed evidence record.
- A subsequent read-only readiness check also observes the record in the destination.
- The source WAL remains present and uncheckpointed for the duration of the snapshot test.
- The temporary snapshot main file and any `-wal`, `-shm`, or `-journal` sidecars are removed after publication or failure.

## Compatibility and safety

The production change is limited to temporary-artifact cleanup in the snapshot `finally` block. After all snapshot connections have closed, cleanup removes SQLite sidecars associated with the private temporary filename before removing the temporary database itself. The CLI, published JSON Schema, and success/error report contracts are unchanged.

## Validation

Run `validate_patch.ps1`, then inspect the staged diff and run `git diff --cached --check` before committing. The validation script runs focused and related Backup/Restore tests, Ruff, Mypy, JSON Schema syntax validation, the full pytest suite, and the deprecation-warning gate.
