# Part 11-105: WAL Checkpoint Readiness Observation Contract

## Purpose

Verify that database readiness checks are observational while a WAL writer has staged uncommitted schema and `user_version` changes, including repeated expected index-name collisions inside SAVEPOINTs. Readiness commands must not commit the writer, checkpoint the WAL, expose the uncommitted index, or alter the source/destination artifact set.

## Contract

- Both backup-destination and restore-destination flows are covered.
- A reader pins the committed baseline while a writer opens an immediate transaction, changes `user_version`, creates a probe index, and attempts the existing required replay-claim index three times.
- Every name collision returns the same `already exists` error. Rolling back each SAVEPOINT restores the writer's outer marker and preserves the required index.
- Three API readiness checks and two JSON CLI checks run while the writer transaction is still open. Each reports the committed baseline, produces deterministic JSON with empty stderr, and leaves the main database and WAL bytes unchanged during the observation window.
- The readiness checks neither commit the transaction nor make the staged probe index visible to the pinned reader. After the writer commits, the old reader continues to see its original snapshot.
- `TRUNCATE` checkpoint retries stay busy while the reader pins the old snapshot. After the reader exits, the checkpoint returns `(0, 0, 0)`.
- Source/backup bytes and synthetic `.partial`, `-wal`, `-shm`, and `-journal` residual artifacts remain unchanged. Readiness reports remain stable after checkpoint completion.

## Scope

This part adds one focused test and this operations note only. Production code, CLI behavior, the published JSON report, and the published JSON Schema are unchanged.

## Validation

Run `validate_patch.ps1` from the SH-3 repository root with Python 3.12+ selected through `SH3_PYTHON`. The validator runs the new contract, related WAL/index/recovery and JSON CLI regressions, Ruff, Mypy, published JSON Schema parsing, full pytest, the deprecation-warning gate, whitespace validation, and `git diff --check`.
