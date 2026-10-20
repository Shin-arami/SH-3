# Part 11-57 - Persistent Replay Backup/Restore Invalid-Source Preflight Contract

## Purpose

Parts 11-54 through 11-56 cover normalized source/destination identity, cleanup after temporary snapshot failures, and atomic publication races. This part covers a different boundary: an existing input path is not necessarily a valid SH-3 SQLite database. Backup and restore must fail during read-only source preflight before creating destination directories or snapshot artifacts.

## Contract

Process-level tests run both `backup` and `restore` with an existing input file containing invalid SQLite bytes and JSON output enabled.

- Each operation exits with code `1` and emits exactly one stable JSON error envelope.
- The error envelope identifies the action and `readiness_check_failed` / `PersistentReplayReadinessError`.
- Standard error provides a stable diagnostic without a traceback or full source/destination paths.
- The input file remains present and byte-for-byte unchanged.
- The destination and its initially absent parent directory remain absent, proving preflight happens before destination preparation.

## Compatibility and safety

This part adds tests and documentation only. It does not alter production code, CLI parsing, the error envelope, or the published JSON Schema. Each input is a private temporary file containing deterministic non-SQLite bytes; no concurrency or filesystem timing is required.

## Validation

Run `validate_patch.ps1`, then inspect the staged diff and run `git diff --cached --check` before committing. The validation script runs focused and related Backup/Restore tests, Ruff, Mypy, JSON Schema syntax validation, the full pytest suite, and the deprecation-warning gate.
