# Part 11-71 - Persistent Replay Recovery Check State Transition Contract

## Purpose

Part 11-70 verifies that repeated read-only checks produce stable reports while residual snapshot artifacts remain. This part exercises the complementary transition: the check must clearly fail while a required schema index is absent, then return to a stable passing state only after an explicit schema repair.

## Contract

The contract is exercised for backup-destination and restore-destination scenarios. It verifies that:

- a database with the required `sh3_replay_claims_state_idx` removed returns the existing JSON error envelope, a nonzero exit code, and a diagnostic that does not expose absolute paths;
- the failed check does not repair or otherwise mutate the database or associated residual `.partial` artifacts;
- an explicit repair restores the required index and allows subsequent `check --json` commands to pass;
- three successful checks after repair return identical reports;
- source and repaired destination bytes remain unchanged during the checks;
- all synthetic `.partial`, `.partial-wal`, `.partial-shm`, and `.partial-journal` artifacts remain present with unchanged contents throughout the failed and successful checks.

## Compatibility and safety

This part adds a contract test and operations documentation only. Production code, CLI arguments, JSON report fields, and the published JSON Schema are unchanged. The test deliberately performs its schema mutation and repair inside pytest's temporary directory; `check --json` itself remains read-only.

## Operator recovery

A failed readiness check is evidence that the current database has not passed validation; it is not permission for the checker to mutate the database. Preserve residual artifacts, carry out an explicit and independently justified repair, then re-run the read-only check. A stable success after repair confirms the repaired database is readable and consistent under this check, but does not by itself authorize deletion of residual artifacts.

## Validation

Run `validate_patch.ps1` from the SH-3 repository root using Python 3.12+. The script runs the state-transition test, related Backup/Restore and JSON CLI regressions, Ruff, Mypy, published JSON Schema syntax validation, the full pytest suite, the deprecation-warning gate, and whitespace validation.
