# Part 11-99 — WAL Reader Release Order Contract

## Purpose

This contract verifies that WAL checkpoint completion follows the oldest still-active reader snapshot rather than the order in which readers are closed. It complements Part 11-98 by releasing readers in the reverse order: the newer/intermediate reader is closed first while the oldest reader remains active.

The contract is exercised for both backup destinations and restore destinations. It adds a test and this operations document only; production code, CLI behavior, report format, and published JSON Schema remain unchanged.

## Required behavior

1. Create a WAL-mode destination and pin an oldest reader to the initial committed epoch.
2. Commit a first write epoch and pin a second reader to that intermediate epoch.
3. Commit a second write epoch while repeatedly attempting the required-index collision inside a savepoint. Each collision must fail consistently and roll back only the savepoint-local mutation.
4. While both readers are active, repeated `wal_checkpoint(TRUNCATE)` calls must remain busy and preserve both reader snapshots.
5. Close the newer/intermediate reader first. The oldest reader still pins the earlier snapshot, so repeated TRUNCATE attempts must remain busy and must not expose either later epoch to that reader.
6. Close the oldest reader. The same writer connection must then complete TRUNCATE and observe `(0, 0, 0)`.
7. Confirm both committed write epochs and both probe indexes remain present, while the required index keeps its canonical table, column order, and attributes.
8. Confirm the readiness-check JSON report is deterministic, stderr remains empty, and source, backup, and residual `.partial` artifacts remain unchanged.

## Running the contract

Run `validate_patch.ps1` from the repository root with the Python 3.12+ interpreter selected via `SH3_PYTHON`. The script runs the focused contract, related WAL/index/recovery/JSON CLI regressions, Ruff, Mypy, published JSON Schema parsing, the full pytest suite, the deprecation-warning gate, whitespace validation, and `git diff --check`.

## Operational boundary

This is a test-only contract. It does not alter readiness behavior, make the checker perform repairs, modify database schemas, or change CLI or JSON Schema contracts.
