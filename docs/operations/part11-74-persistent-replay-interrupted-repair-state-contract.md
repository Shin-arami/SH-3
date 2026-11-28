# Part 11-74 - Persistent Replay Interrupted Repair State Contract

## Purpose

Part 11-71 through Part 11-73 exercise missing-index failures, explicit repair, and repeated recovery cycles. This part adds a different interrupted-repair state: the required index exists, but has the wrong ordered columns. The check must recognize this as invalid rather than treating index presence as sufficient.

## Contract

The test runs for backup-destination and restore-destination scenarios. It verifies that:

- the index is replaced with an incorrect key order to model a repair interrupted before canonical schema restoration;
- three consecutive `check --json` calls fail with the established JSON error envelope and stable diagnostic;
- the failed checks do not auto-repair the index or mutate database bytes and residual `.partial`, `.partial-wal`, `.partial-shm`, or `.partial-journal` artifacts;
- diagnostics do not disclose absolute source, backup, or destination paths;
- after an explicit repair restores the canonical index column order, two consecutive checks return identical successful reports;
- the successful checks preserve source bytes, repaired destination bytes, and residual artifact contents.

## Compatibility and safety

This part adds only a contract test and operations documentation. Production code, CLI arguments, JSON report fields, and the published JSON Schema are unchanged. All schema changes are performed explicitly by the test under pytest's temporary directory; the readiness checker itself remains read-only.

## Operator recovery

An index name alone does not establish schema correctness: the required index must also have its exact ordered columns. If a repair is interrupted and the index exists in an invalid form, retain residual artifacts and keep treating readiness checks as failed until the schema repair is completed explicitly. Repeated failures are expected to be deterministic and must not mutate the database or evidence files.

## Validation

Run `validate_patch.ps1` from the SH-3 repository root with Python 3.12+. It runs this contract, related recovery and JSON CLI regression tests, Ruff, Mypy, published JSON Schema syntax validation, the full pytest suite, the deprecation-warning gate, whitespace validation, and `git diff --check`.
