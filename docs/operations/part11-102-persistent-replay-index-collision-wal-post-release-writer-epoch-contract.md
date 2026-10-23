# Part 11-102: Persistent Replay WAL Post-Release Writer Epoch Contract

## Purpose

Verify that an additional committed writer epoch remains correctly isolated after an intermediate WAL reader releases its snapshot while an older reader still pins the oldest epoch. Checkpoint retries must account for the expanded WAL history and only complete after the remaining reader releases.

## Scope

- Both backup destinations and restore destinations are covered.
- Two readers retain snapshots from the original and first committed writer epochs.
- The checkpoint mode matrix is exercised while both readers are active; `PASSIVE` returns without waiting, while `FULL`, `RESTART`, and `TRUNCATE` report the pinned reader state.
- A third writer epoch is committed after the initial checkpoint attempts; repeated required-index collision attempts are contained by SAVEPOINT and preserve the canonical index.
- The newer reader is released first. The older reader continues to pin the checkpoint, so the strong checkpoint modes remain busy.
- A fourth writer epoch is then committed while the older reader remains active. It creates a distinct probe index and advances `user_version`; three repeated attempts to recreate the required index fail consistently inside SAVEPOINT scopes.
- The fourth epoch increases the WAL log frame count. The oldest reader continues to see its original snapshot and cannot see any probe indexes introduced by writers.
- Once the oldest reader releases, `FULL` and `RESTART` process all remaining frames and `TRUNCATE` returns `(0, 0, 0)`.
- All four committed writer epochs, the canonical required-index definition, readiness JSON, protected source/backup bytes, and residual `.partial` artifacts remain stable.

## Validation

Run `validate_patch.ps1` from the SH-3 repository root with Python 3.12+ selected by `SH3_PYTHON`. The validator runs this contract, related WAL/index/recovery and JSON CLI regressions, Ruff, Mypy, published JSON Schema parsing, the full pytest suite, the deprecation-warning gate, whitespace validation, and `git diff --check`.

This part adds only one contract test and one operations document. No production implementation, CLI behavior, published JSON report, or JSON Schema is changed.
