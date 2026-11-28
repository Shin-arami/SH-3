# Part 11-119 — WAL Snapshot Multiple Cleanup-Failure Aggregation Contract

## Scope

This part adds a contract test and operations note only. Production code, CLI behavior, and the published JSON Schema remain unchanged.

## Contract

The test injects two independent unlink failures during the final cleanup of a successfully published backup or restore snapshot: the temporary snapshot's WAL sidecar and the temporary snapshot's main `.partial` path. A separate temporary journal sidecar is permitted to clean up normally.

The contract requires `_create_verified_snapshot` to attempt every cleanup path, report the aggregate count as two failed items, preserve the first `PermissionError` as the chained cause, and retain actionable recovery guidance. A cleanup failure must not invalidate or replace the already-published destination. Artifacts that could not be removed remain available for inspection; artifacts whose cleanup succeeds are removed. After manual removal of the orphaned names, a retry to a new destination must succeed while the original published database remains valid.

The test covers both `backup_database` and `restore_database`. It uses a WAL-like sidecar fixture at the temporary snapshot path after snapshot verification and publication, so the failure is deterministic and does not require filesystem permission changes.

## Validation

Run `validate_patch.ps1` from the repository root. The validator checks the focused contract, related snapshot/publication/cleanup regressions, Ruff, Mypy, JSON Schema syntax, full pytest, the deprecation-warning gate, whitespace, and `git diff --check`.
