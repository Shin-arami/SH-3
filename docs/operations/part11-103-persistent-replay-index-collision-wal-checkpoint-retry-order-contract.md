# Part 11-103: Persistent Replay WAL Checkpoint Retry Order Contract

## Purpose

Verify that SQLite WAL checkpoint retries remain correct when checkpoint modes are exercised in a different order while readers hold snapshots from distinct committed epochs. The order is intentionally changed from the preceding matrix contract so mode semantics do not depend on a particular attempt sequence.

## Scope

- Backup and Restore destinations are both exercised.
- Two reader connections pin different committed snapshots while two writer epochs publish probe indexes and distinct `user_version` markers.
- With both readers active, checkpoint attempts run in the order `TRUNCATE`, `RESTART`, `FULL`, `PASSIVE`. The strong modes report a pinned reader, while `PASSIVE` returns without waiting and leaves frames uncheckpointed.
- After releasing the newer reader first, strong retries run in the order `RESTART`, `TRUNCATE`, `FULL`; the oldest reader continues to pin the checkpoint.
- After releasing the oldest reader, successful checkpoint retries run in the order `RESTART`, `FULL`, `TRUNCATE`. The final `TRUNCATE` returns `(0, 0, 0)` and empties the WAL when the WAL file remains present.
- Repeated required-index creation collisions remain isolated by SAVEPOINT and preserve the canonical index, committed writer epochs, and claim count.
- Readiness JSON, protected source/backup bytes, and residual `.partial` artifacts remain stable.

## Validation

Run `validate_patch.ps1` from the SH-3 repository root with Python 3.12+ selected through `SH3_PYTHON`. The validator runs this contract, related WAL/index/recovery and JSON CLI regressions, Ruff, Mypy, published JSON Schema parsing, the full pytest suite, the deprecation-warning gate, whitespace validation, and `git diff --check`.

No production implementation, CLI behavior, published JSON report, or JSON Schema is changed by this part.
