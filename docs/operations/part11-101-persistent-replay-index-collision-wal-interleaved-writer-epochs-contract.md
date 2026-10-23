# Part 11-101: Persistent Replay WAL Interleaved Writer Epochs Contract

## Purpose

Verify that a new committed writer epoch introduced after a first round of WAL checkpoint attempts remains consistent with readers pinned to earlier snapshots, and that all checkpoint modes are retried correctly across the expanded WAL history.

## Scope

- Backup and Restore destinations are both exercised.
- Two readers are pinned to the original and first committed writer epochs.
- The first checkpoint-mode matrix runs while both readers are active: `PASSIVE` returns without waiting but cannot process all frames; `FULL`, `RESTART`, and `TRUNCATE` report a busy reader epoch.
- A third writer epoch is committed after those checkpoint attempts. It creates a distinct probe index and updates `user_version`; repeated attempts to create the required index inside SAVEPOINT scopes still fail consistently and do not disturb the canonical index.
- Both readers keep their original views after the third writer epoch commits. A second checkpoint-mode matrix confirms that `PASSIVE` still returns without waiting, strong modes remain busy, and the WAL log frame count has grown to cover the interleaved writes.
- Releasing the newer reader first remains insufficient because the older reader still pins the oldest snapshot. After the oldest reader is released, `FULL` and `RESTART` process all remaining frames and `TRUNCATE` returns `(0, 0, 0)`.
- The three committed writer epochs, index definitions, readiness JSON, protected source/backup bytes, and residual `.partial` artifacts remain stable.

## Validation

Run `validate_patch.ps1` from the SH-3 repository root with the Python 3.12+ interpreter selected by `SH3_PYTHON`. The validator runs this contract, related WAL/index/recovery and JSON CLI regressions, Ruff, Mypy, published JSON Schema parsing, the full pytest suite, the deprecation-warning gate, whitespace validation, and `git diff --check`.

No production implementation, CLI behavior, published JSON report, or JSON Schema is changed by this part.
