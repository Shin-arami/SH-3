# Part 11-118 — WAL Snapshot Published Destination and Cleanup Failure Contract

## Purpose

Verify the success-publication / cleanup-failure boundary for both backup and restore. The snapshot destination may already be published when removal of the temporary `.partial` name fails, so callers must receive a cleanup error without losing or corrupting the destination.

## Contract

- The test deterministically injects a failure only when unlinking the temporary snapshot's main `.partial` path; SQLite sidecar cleanup is allowed to complete.
- Since publication has already succeeded, the operation raises an `OSError` that states the snapshot was published but temporary cleanup was incomplete, with the injected unlink error preserved as its cause.
- The published destination remains a valid database with the expected replay-claim index and record counts.
- The orphan `.partial` name and the published destination refer to the same file until the orphan name is explicitly removed; sidecars are cleaned before the main temporary file unlink is attempted.
- Removing the orphan name does not remove or mutate the published destination.
- A subsequent backup or restore to a fresh destination succeeds, while source and restore-input database artifacts remain unchanged.

## Scope

This patch adds only a contract test and this operations document. It does not change production code, CLI behavior, or the published JSON Schema. The test covers both backup and restore destination paths without relying on thread timing.

## Validation

Run `validate_patch.ps1` from the SH-3 repository root. It runs the focused test, related WAL snapshot/publication/cleanup regressions, Ruff, Mypy, published JSON Schema syntax validation, the full pytest suite, the deprecation-warning gate, whitespace checks, and `git diff --check`.
