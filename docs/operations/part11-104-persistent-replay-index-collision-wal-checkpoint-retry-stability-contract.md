# Part 11-104: Persistent Replay WAL Checkpoint Retry Stability Contract

## Purpose

Verify that successful WAL checkpoint operations remain stable across repeated write epochs and three permutations of the `PASSIVE`, `FULL`, `RESTART`, and `TRUNCATE` modes. The test ensures each mode follows a fresh, committed write epoch instead of accidentally testing later modes only against an empty WAL left by an earlier truncation.

## Scope

- Both backup-destination and restore-destination flows are covered.
- Twelve committed writer epochs are executed across three different checkpoint-mode orders.
- Each epoch commits a unique `user_version` marker and a uniquely named probe index, then attempts to create the already-existing required replay-claim state index three times inside a SAVEPOINT.
- Each collision must raise the same `already exists` error. Rolling back and releasing the SAVEPOINT restores the epoch marker and preserves the probe index, claim count, and canonical required index definition.
- Each epoch is followed immediately by one checkpoint mode. With no active reader, each checkpoint reports `busy = 0` and all reported WAL frames are checkpointed. `TRUNCATE` reports `(0, 0, 0)`.
- A final `TRUNCATE` also returns `(0, 0, 0)`, and every committed probe index and the final epoch marker remain present.
- Readiness JSON is stable over repeated checks. Source/backup bytes and synthetic `.partial`, `-wal`, `-shm`, and `-journal` residual artifacts remain unchanged.

## Validation

Run `validate_patch.ps1` from the SH-3 repository root using Python 3.12+ selected through `SH3_PYTHON`. The validator runs the new contract and related WAL/index/recovery and JSON CLI regressions, Ruff, Mypy, published JSON Schema parsing, full pytest, the deprecation-warning gate, whitespace validation, and `git diff --check`.

This part adds one test and this operations document only. Production code, CLI behavior, the published JSON report, and the JSON Schema are unchanged.
