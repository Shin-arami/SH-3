# Part 11-37 — Persistent Replay JSON Backup/Restore Reports

## Purpose

Part 11-35 introduced JSON output for readiness checks, and Part 11-36 standardized JSON error envelopes for failed checks. The backup and restore commands need the same machine-readable contract so maintenance automation does not have to parse human-oriented text.

## Changes

The `backup` and `restore` subcommands accept `--json`.

- A successful operation writes one JSON object to stdout using the same schema version and summary fields as `check`, with `action` set to `backup` or `restore`.
- Without `--json`, existing text output remains unchanged.
- Failures with `--json` write a single error envelope to stdout and retain detailed diagnostics on stderr. The envelope's `action` identifies the command, and `exit_code` matches the returned code (`1` for operation errors).
- Existing-destination failures use the stable `destination_exists` error code. The operation continues to refuse overwriting an existing destination.
- Error envelopes omit resolved filesystem paths and exception messages. Successful reports retain the destination database path, matching the established success-report behavior.

## Safety boundary

JSON reporting changes presentation only. Backup/restore still verify source and snapshot integrity, refuse to overwrite destination files, and do not modify replay claim semantics. The JSON envelope is not a substitute for checking the process exit code.

## Tests

Tests cover JSON success reports for backup and restore, parseable error envelopes, destination non-overwrite behavior, path suppression in error JSON, and unchanged text output when `--json` is omitted.
