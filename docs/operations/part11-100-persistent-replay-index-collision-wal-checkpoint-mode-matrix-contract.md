# Part 11-100: Persistent Replay WAL Checkpoint Mode Matrix Contract

## Purpose

Verify that SQLite WAL checkpoint modes respect two readers pinned to different committed epochs, that checkpoint progress does not rewrite reader snapshots, and that strong checkpoints complete only after both readers release their transactions.

## Scope

- Backup and Restore destinations are both exercised.
- Two committed writer epochs introduce distinct probe indexes and `user_version` markers. Repeated attempts to create the required index name are rejected inside SAVEPOINT scopes and do not alter the canonical index.
- With both readers active, `PASSIVE` returns without waiting but cannot process the entire WAL; `FULL`, `RESTART`, and `TRUNCATE` report a busy reader epoch.
- Releasing the newer reader first is insufficient while the older reader remains pinned: `FULL`, `RESTART`, and `TRUNCATE` remain incomplete.
- Once both readers are released, `FULL` and `RESTART` checkpoint all remaining frames, and `TRUNCATE` returns `(0, 0, 0)` with an empty WAL file when it remains present.
- Readiness JSON, protected source/backup bytes, the required index definition, and residual `.partial` artifacts remain stable.

## Validation

Run `validate_patch.ps1` from the SH-3 repository root with the Python 3.12+ interpreter selected by `SH3_PYTHON`. The validator runs the contract test, related WAL/index/recovery and JSON CLI regressions, Ruff, Mypy, published JSON Schema parsing, the full pytest suite, the deprecation-warning gate, whitespace validation, and `git diff --check`.

No production implementation, CLI behavior, published JSON report, or JSON Schema is changed by this part.
