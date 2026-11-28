# Part 11-59 - Persistent Replay Backup/Restore Semantic-Source Preflight Contract

## Purpose

Part 11-57 verifies preflight rejection for an input file that is not a SQLite database. This part covers a distinct condition: the input is a structurally readable SH-3 SQLite database, but its stored evidence fails application-level integrity verification. Backup and restore must reject the source before destination preparation.

## Contract

Process-level tests exercise both `backup` and `restore` with a database whose evidence record payload has been changed without updating its integrity digest.

- Each operation exits with code `1` and emits exactly one stable JSON error envelope.
- The envelope identifies the operation and `readiness_check_failed` / `PersistentReplayReadinessError`.
- Standard error reports the stable evidence-integrity diagnostic without a traceback or full source/destination paths.
- The source remains byte-for-byte unchanged by the rejected operation.
- The destination parent directory, destination file, and temporary snapshot artifacts remain absent.

## Compatibility and safety

This part adds tests and documentation only. It does not change production code, CLI parsing, error envelopes, or the published JSON Schema. The source remains a valid SQLite file; only the application-level evidence content is deliberately tampered with in an isolated temporary database.

## Validation

Run `validate_patch.ps1`, then inspect the staged diff and run `git diff --cached --check` before committing. The validation script runs the focused and related Backup/Restore tests, Ruff, Mypy, JSON Schema syntax validation, the full pytest suite, and the deprecation-warning gate.
