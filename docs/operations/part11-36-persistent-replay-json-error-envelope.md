# Part 11-36 — Persistent Replay JSON Error Envelope

## Purpose

Part 11-35 made successful readiness checks machine-readable. A caller using `--json` must also be able to distinguish an unsuccessful database/readiness inspection without attempting to parse human-oriented diagnostics from stderr or receiving empty stdout.

## Changes

For `check --json`, exceptions raised during database lookup or readiness inspection now produce one JSON error envelope on stdout. Existing human-readable diagnostics remain on stderr. Without `--json`, the current text-only error behavior is unchanged.

The envelope contains:

- `schema_version`: `1`.
- `action`: `check`.
- `integrity_status`: `error`, meaning the readiness report could not be completed; it does not by itself assert that SQLite data is corrupt.
- `error.code`: a stable category such as `database_not_found`, `permission_denied`, `sqlite_error`, `invalid_argument`, `operating_system_error`, or `readiness_check_failed`.
- `error.type`: the Python exception class name for diagnostics that do not reveal exception messages or filesystem paths on stdout.
- `policy_gates`: an empty object because policy-gate outcomes are not evaluated when the readiness inspection fails.
- `exit_code`: `1`, matching the CLI's existing operational-error behavior.

The envelope intentionally excludes the exception message and resolved database path. Detailed error text is preserved on stderr. Command-line syntax errors rejected by `argparse` occur before the command runs and retain argparse's existing behavior.

## Safety boundary

The error envelope is observational and read-only. It does not repair the database or alter replay claims. JSON stdout contains one parseable object; diagnostics remain separate on stderr. Exit-code semantics for successful checks and policy-gate failures (`2` and `3`) are unchanged.

## Tests

Tests cover a missing database and an incomplete SH-3 schema. They verify the error envelope, matching exit code, stable error categories, separation of JSON stdout from diagnostics, and suppression of the resolved database path in JSON output.
