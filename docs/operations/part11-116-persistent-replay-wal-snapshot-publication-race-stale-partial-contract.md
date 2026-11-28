# Part 11-116 — WAL Snapshot Publication Race and Stale Partial Isolation Contract

## Status

Contract test and operations documentation only. No production module, CLI contract, or published JSON Schema is changed.

## Purpose

Verify that a destination appearing at the final hard-link publication boundary cannot be overwritten, and that a failed publication does not remove or mutate pre-existing `.partial` files or their SQLite sidecars. After the simulated competing publisher is explicitly removed, a retry must publish a valid snapshot while leaving all pre-existing stale artifacts unchanged.

## Scenarios

- Backup to a new destination while a competing publisher creates the destination immediately before `os.link`.
- Restore to a new destination under the same publication race.
- Inspect publication failure behavior and confirm the competing destination's bytes remain unchanged.
- Verify that the temporary snapshot created by the failed attempt is cleaned, while pre-existing stale `.partial`, `-wal`, `-shm`, and `-journal` artifacts retain their original bytes.
- Explicitly remove only the test's simulated competing destination and retry publication successfully.
- Re-run `check --json` twice and compare the complete reports, while verifying source/input snapshot bytes and stale artifacts remain unchanged.

## Operational contract

1. Publication must be atomic and must not overwrite a destination created by a competing process.
2. Cleanup after a failed attempt owns only temporary artifacts created by that attempt.
3. Unrelated stale artifacts must not be silently deleted or adopted as a successful snapshot.
4. An operator must explicitly resolve a destination conflict before retrying; retry must produce a fresh, verified snapshot.
5. Backup source and restore input snapshots remain byte-for-byte unchanged.

## Validation

`validate_patch.ps1` runs the focused contract test, related WAL snapshot/publication/recovery regression tests, Ruff, Mypy, published JSON Schema syntax validation, the full pytest suite, a DeprecationWarning-as-error gate, whitespace checks, and `git diff --check`.
