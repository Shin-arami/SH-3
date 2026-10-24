# Part 11-134 — Destination configuration failure with multiple connection-close failures

## Purpose

Verify exception precedence and connection ownership when SQLite opens both an owned source connection and a temporary destination connection, destination `PRAGMA busy_timeout` setup fails, and close operations also fail.

## Contract

For the owned-source path, the destination configuration error remains the `PersistentReplayReadinessError` cause. Closing both destination and source connections is attempted, and one diagnostic note aggregates both close failures. For the borrowed-source path, the caller-owned source connection remains open and usable; only the destination close error is reported. Online backup does not proceed in either case.

The helper-level test leaves outer temporary-file removal to its caller, so the test explicitly removes the temporary path after assertions. It does not alter source data.

## Scope

This part adds only a focused test and this operations note. Production code, CLI output, and the published JSON Schema remain unchanged.

## Recovery

Preserve the first operational failure as the primary cause. Connection cleanup failures should be recorded as diagnostic notes without skipping remaining closes or taking ownership of a borrowed source connection.
