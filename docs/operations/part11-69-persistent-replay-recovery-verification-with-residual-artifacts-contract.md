# Part 11-69 - Persistent Replay Recovery Verification with Residual Artifacts Contract

## Purpose

Part 11-68 verifies that a backup/restore retry which refuses to overwrite an existing destination preserves all pre-existing `.partial` snapshot artifacts and SQLite sidecars. This part covers the read-only verification step that should inform the recovery decision: an operator must be able to run the published `check --json` command against the destination while those residual artifacts remain, without the check mutating either database or any residual artifact.

## Contract

A deterministic test runs the check command for both backup- and restore-labelled scenarios and asserts that:

- the existing destination passes the public read-only check and returns the established single-line JSON report;
- the report's schema version, action, database path, integrity status, counts, policy gates, and exit code retain their existing public contract;
- the source and destination database bytes remain unchanged;
- the exact set of residual `.partial`, `.partial-wal`, `.partial-shm`, and `.partial-journal` artifacts remains unchanged;
- every residual artifact remains present and byte-for-byte identical;
- re-checking the destination after the CLI command returns the same readiness counts.

## Recovery guidance

A successful `check --json` establishes that the destination currently passes the readiness checks; it does not prove that stale temporary artifacts can be safely deleted. Preserve residual artifacts while diagnosing an interrupted operation. Only perform explicit cleanup after independently verifying the destination and determining which artifacts belong to the failed attempt. An overwrite refusal remains the guard against an unsafe retry.

## Compatibility and safety

This is a test and operations-documentation addition only. Production code, CLI arguments, JSON report fields, and the published JSON Schema are unchanged. The test uses isolated temporary SQLite databases and synthetic residual artifacts under pytest's temporary directory.

## Validation

Run `validate_patch.ps1` from the repository root with Python 3.12+. It runs the new contract, related Backup/Restore and JSON CLI regressions, Ruff, Mypy, published JSON Schema syntax validation, the full pytest suite, the deprecation-warning gate, and `git diff --check`.
