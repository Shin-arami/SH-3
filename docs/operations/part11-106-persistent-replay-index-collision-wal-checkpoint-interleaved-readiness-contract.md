# Part 11-106: WAL Checkpoint Interleaving Readiness Contract

## Purpose

Verify that readiness checks remain observational when WAL checkpoint attempts run on a separate SQLite connection between repeated API and JSON CLI checks. Checkpoint operations may legitimately update the database and WAL; the contract captures the post-checkpoint image and proves that readiness observation itself does not alter either file.

## Contract

- Both backup-destination and restore-destination flows are covered.
- A reader pins the previously committed snapshot while a writer stages a `user_version` change and probe index, including three repeated expected collisions on the required replay-claim index inside SAVEPOINTs.
- After the writer commits, a separate checkpoint connection attempts `PASSIVE`, `FULL`, `RESTART`, and `TRUNCATE` in a deliberately interleaved retry order while the old reader remains active.
- `PASSIVE` returns without waiting. Stronger modes report that completion remains blocked by the older reader, and the reader continues to see the original marker and schema.
- After every checkpoint attempt, the test captures the database and WAL bytes, calls `check_database`, and proves the API check leaves both files unchanged. Selected iterations also invoke the JSON CLI and verify the same non-mutating property.
- JSON reports remain stable, stderr is empty, and the readiness calls neither commit work nor repair, mutate, or checkpoint the database.
- Source/backup bytes and synthetic `.partial`, `-wal`, `-shm`, and `-journal` residual artifacts remain unchanged.
- After the old reader rolls back and closes, `TRUNCATE` completes with `(0, 0, 0)`, and post-checkpoint readiness reports remain deterministic.

## Scope

This part adds one focused test and this operations note only. Production code, CLI behavior, the published JSON report, and the published JSON Schema are unchanged.

## Validation

Run `validate_patch.ps1` from the SH-3 repository root with Python 3.12+ selected through `SH3_PYTHON`. The validator runs the new contract, the Part 11-105 observational readiness regression and related WAL/index/recovery and JSON CLI regressions, Ruff, Mypy, published JSON Schema parsing, full pytest, the deprecation-warning gate, whitespace validation, and `git diff --check`.
