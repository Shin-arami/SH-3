# Part 11-60 - Persistent Replay Backup/Restore Prevalidated Snapshot Publication Contract

## Purpose

Parts 11-54 through 11-59 verify path identity, temporary snapshot cleanup, atomic publication races, invalid and semantically corrupt input preflight, WAL snapshot consistency, and related safety contracts. This correction removes a destructive post-publication rollback strategy that relied on checking an inode and later unlinking the same pathname. A concurrent replacement between those operations could cause the cleanup to delete a file no longer owned by this operation.

## Contract

Deterministic tests exercise both `backup` and `restore`.

- The source is checked before snapshot creation.
- The private temporary snapshot is checked before publication.
- Publication succeeds only through the existing atomic no-overwrite hard-link operation.
- The success report uses the metrics from the prevalidated snapshot and reports the final destination path.
- The destination is not reopened for a second readiness check after publication, and no path-based rollback deletes a potentially replaced destination.
- Temporary snapshot files and SQLite sidecars are removed after publication.
- The source remains byte-for-byte unchanged.

## Compatibility and safety

This is a narrow production correction. The temporary snapshot's `DatabaseReadinessReport` is retained and returned with only `database_path` replaced after atomic publication succeeds. This is valid because the hard link publishes the same inode that was just verified. It removes the check-then-unlink time-of-check/time-of-use race. CLI arguments, published JSON Schema, and success/error envelope shapes remain unchanged.

## Validation

Run `validate_patch.ps1`, inspect the production diff and staged changes, and run `git diff --cached --check` before committing. The validation script covers this contract, related Backup/Restore safety regressions, Ruff, Mypy, JSON Schema syntax, the full pytest suite, and the deprecation-warning gate.
