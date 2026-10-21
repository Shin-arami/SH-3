# Part 11-63 - Persistent Replay Connection Ownership and Close-Failure Contract

## Purpose

Part 11-62 keeps one caller-owned, read-only source connection for preflight and online backup. Review of `_backup_to_temporary` found that its `finally` block closed the destination connection before closing an internally created source connection in the same sequential block. If destination `close()` raised, the source connection's close call could be skipped.

## Contract

- The helper must attempt to close a source connection it created itself even when destination connection cleanup raises.
- The helper must not close a source connection supplied by its caller; ownership remains with the caller.
- A destination-close failure is propagated, and it must not bypass the owned-source cleanup path.
- The behavior is tested deterministically for both owned and borrowed source connections using SQLite connection subclasses that inject a destination-close error.
- This part does not change CLI arguments, report envelopes, or the published JSON Schema.

## Implementation

Destination cleanup is guarded by a nested `try/finally`. This ensures the source close attempt runs even if destination close raises, while preserving the existing `owns_source_connection` rule for caller-provided connections.

## Validation

Run `validate_patch.ps1`. It executes the new connection ownership contract, related Part 11-55/60/61/62 Backup/Restore regressions, Ruff, Mypy, published JSON Schema syntax validation, the full pytest suite, and the deprecation-warning gate. Inspect the final diff and run `git diff --check` before committing.
