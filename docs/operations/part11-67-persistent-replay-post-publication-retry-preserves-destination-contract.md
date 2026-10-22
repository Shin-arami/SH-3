# Part 11-67 - Persistent Replay Post-Publication Retry Destination Contract

## Purpose

Part 11-66 established that a WAL sidecar cleanup error can occur after a destination snapshot has already been published. This part covers the next operator-facing boundary: retrying the same backup or restore command must not overwrite the destination that was published by the first attempt.

## Contract

A deterministic fault-injection test runs both `backup` and `restore` and enforces that:

- the first invocation publishes a readable destination but exits with the existing sanitized cleanup-error report when temporary WAL cleanup fails;
- retrying the identical command fails closed instead of replacing an already-published destination;
- the destination's bytes and verified evidence/replay-claim counts remain unchanged across the retry;
- the source bytes remain unchanged;
- the injected residual WAL sidecar remains observable across the retry, so the test does not accidentally hide the original ambiguous-cleanup condition;
- JSON output remains one report per invocation with the established top-level fields; standard-error exception messages and notes redact absolute paths, while retaining the error classification and recovery guidance;
- test teardown removes the deliberately injected sidecar.

## Compatibility and safety

The path-redaction correction updates the existing standard-error diagnostic renderer to mask absolute file-system paths in exception messages and exception notes. CLI arguments, JSON report keys, and the published JSON Schema remain unchanged. The regression test continues to assert the existing no-overwrite publication behavior without requiring a specific low-level error subtype for an existing destination.

## Operator recovery

When an operation reports that publication succeeded but temporary cleanup was incomplete, first verify the published destination and inspect matching `.partial` files and SQLite sidecars. Do not blindly rerun the command: the original destination may already exist. Resolve filesystem or handle-access problems, then choose an explicit recovery action based on the verified destination state.

## Validation

Run `validate_patch.ps1` from the repository root with Python 3.12+. The script runs this contract, related Backup/Restore safety tests, Ruff, Mypy, published JSON Schema syntax validation, the full pytest suite, the deprecation-warning gate, and `git diff --check`.
