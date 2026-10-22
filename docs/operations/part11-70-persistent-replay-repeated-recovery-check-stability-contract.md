# Part 11-70 - Persistent Replay Repeated Recovery Check Stability Contract

## Purpose

Part 11-69 establishes that a read-only `check --json` verification can inspect a published destination while residual `.partial` snapshot artifacts and SQLite sidecars remain beside it. This part repeats that check three times to verify that diagnostic output and recovery evidence remain stable across consecutive verification attempts.

## Contract

The test runs for both the backup and restore recovery scenarios and verifies that:

- each `check --json` invocation exits successfully and emits exactly one parseable JSON object on stdout with no stderr output;
- the full JSON report remains identical across three consecutive invocations, including database identity, SQLite version, journal mode, integrity status, record counts, policy gates, and exit code;
- source and destination database bytes remain unchanged;
- each synthetic `.partial`, `.partial-wal`, `.partial-shm`, and `.partial-journal` artifact remains present with byte-for-byte identical content;
- the exact residual artifact set remains unchanged after each invocation;
- a final read-only readiness check reports the same SQLite mode and evidence/claim counts as the initial check.

## Compatibility and safety

This is a test and operations-documentation addition only. Production code, CLI arguments, JSON report fields, and the published JSON Schema are unchanged. Test artifacts are created only in pytest's temporary directory.

## Operator recovery

Repeat read-only verification may be used to establish whether the destination is consistently readable, but it does not authorize deletion of residual artifacts. Keep the artifacts intact until the destination has been verified and an explicit recovery/cleanup decision has been made. Repeated identical reports confirm diagnostic stability; they do not independently prove that stale sidecars are safe to delete.

## Validation

Run `validate_patch.ps1` from the SH-3 repository root using Python 3.12+. The script runs the new contract, related Backup/Restore and JSON CLI regressions, Ruff, Mypy, published JSON Schema syntax validation, the full pytest suite, the deprecation-warning gate, and `git diff --check`.
