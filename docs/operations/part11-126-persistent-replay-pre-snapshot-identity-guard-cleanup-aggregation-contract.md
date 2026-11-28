# Part 11-126 — Pre-Snapshot Identity Guard and Cleanup Aggregation Contract

## Scope

This contract covers failure of the source-database identity guard at the `before snapshot creation` phase, after the temporary `.partial` pathname has been allocated but before the online backup is invoked. It additionally injects two cleanup failures so that the original identity error and recovery diagnostics must survive. Both backup and restore flows are tested without production or schema changes.

## Injected scenario

The test captures the temporary pathname returned by `tempfile.mkstemp`, injects a source identity rejection at the pre-snapshot phase, and creates representative WAL and journal sidecars at that temporary name. Deletion of the WAL sidecar and temporary snapshot is made to fail. The online backup, temporary snapshot verification, and publication methods are observed to prove they do not run in this phase.

## Required invariants

- The original `PersistentReplayReadinessError` object remains the raised exception.
- The online backup and publication operations are not called, and the temporary snapshot is never passed to `check_database`.
- Cleanup attempts all sidecars and the temporary snapshot even after the first cleanup failure.
- Both cleanup failures and recovery guidance are preserved in the exception notes.
- The final destination remains absent and source/backup artifacts remain unchanged.
- After removing the injected orphan names, a retry to a fresh destination succeeds.

## Validation

Run `validate_patch.ps1` from the SH-3 repository root with the project's Python 3.12+ interpreter. The script executes the focused contract, related regressions, Ruff, Mypy, published JSON Schema syntax validation, the full pytest suite, the deprecation-warning gate, whitespace checks, and `git diff --check`.

## Compatibility boundary

This patch adds a test and this operations document only. It does not alter `persistent_replay_ops.py`, CLI behavior, operational JSON output, or `persistent-replay-report-v1.schema.json`.
