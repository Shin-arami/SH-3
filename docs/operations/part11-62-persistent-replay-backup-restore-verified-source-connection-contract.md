# Part 11-62 - Persistent Replay Verified Source Connection Contract

## Purpose

Part 11-61 added file-identity checkpoints. A remaining limitation is that a check-by-path followed by an independent open can still separate the object being validated from the object read by the online backup if a path changes between those operations.

## Contract

- Open one read-only SQLite source connection for the operation.
- Run the source readiness checks on that exact connection.
- Reuse the same connection for SQLite's online backup API; do not reopen the source path for the snapshot.
- Retain the Part 11-61 identity checkpoints as fail-closed detection when a source-path identity change is observable.
- Keep destination snapshot verification, atomic no-overwrite publication, cleanup, JSON report shape, CLI arguments, and the published JSON Schema unchanged.
- Exercise both `backup` and `restore`, and assert by connection identity that source preflight and snapshot use the same connection.

## Implementation note

`check_database` gains a private internal `_connection` parameter so operational backup/restore can perform readiness checks against a caller-owned read-only connection. Without that parameter it preserves the ordinary behavior of opening and closing its own connection. `_backup_to_temporary` likewise accepts an optional source connection and only closes source connections that it opened itself. This change does not transfer ownership of the pinned connection to either helper.

## Scope

This ensures that preflight and online snapshot read through the same SQLite connection, preventing the snapshot from silently reopening a different file through a changed pathname. Path identity checks still fail closed when replacement is observable. Filesystem-level durability and the security of the directory against a privileged actor remain separate operational concerns.

## Validation

Run `validate_patch.ps1`, inspect the production and test diffs, and run `git diff --cached --check` before committing. Validation covers the new shared-connection contract, the affected Part 11-55/60/61 regression tests, related Backup/Restore safety contracts, Ruff, Mypy, published JSON Schema syntax, the full pytest suite, and the deprecation-warning gate.
