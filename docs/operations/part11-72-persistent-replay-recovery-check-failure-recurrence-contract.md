# Part 11-72 - Persistent Replay Recovery Check Failure Recurrence Contract

## Purpose

Part 11-71 verifies that a read-only recovery check fails when the required replay-claim state index is missing, succeeds only after an explicit repair, and then remains stable across repeated successful checks. This part verifies the opposite edge of that state machine: the same defect can recur after repair, and every subsequent check must report the failure again without silently repairing the database or modifying residual artifacts.

## Contract

The contract is exercised for backup-destination and restore-destination scenarios. It verifies that:

- the first missing-index check returns the existing sanitized JSON error envelope and a nonzero exit code;
- explicit recreation of `sh3_replay_claims_state_idx` is required before `check --json` succeeds;
- after the index is deliberately dropped again, repeated checks return the same failure report and diagnostic as the initial failure;
- failure diagnostics identify the missing index while redacting absolute source and destination paths;
- each read-only check leaves source bytes, destination bytes, and the exact residual artifact set unchanged;
- synthetic `.partial`, `.partial-wal`, `.partial-shm`, and `.partial-journal` artifacts remain present with byte-for-byte identical content through failure, repair, success, and recurrence.

## Compatibility and safety

This part adds a contract test and operations documentation only. Production code, CLI arguments, JSON report fields, and the published JSON Schema are unchanged. The test performs its deliberate schema mutations only against a database under pytest's temporary directory; the `check --json` command remains read-only and never performs repair.

## Operator recovery

A successful check after repair is a point-in-time result, not a guarantee that the database cannot become invalid again. If a later check reports the same schema defect, treat it as a current failure, preserve residual artifacts, and investigate the cause of recurrence. Do not assume prior success authorizes retrying backup/restore or deleting `.partial` files. Apply explicit, independently justified repair and rerun the check before making a recovery decision.

## Validation

Run `validate_patch.ps1` from the SH-3 repository root using Python 3.12+. The script runs the recurrence test, related recovery and JSON CLI regressions, Ruff, Mypy, published JSON Schema syntax validation, the full pytest suite, the deprecation-warning gate, whitespace validation, and `git diff --check`.
