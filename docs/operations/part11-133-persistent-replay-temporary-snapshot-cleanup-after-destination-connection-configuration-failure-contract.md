# Part 11-133 — Destination connection configuration failure and snapshot cleanup contract

## Purpose

Specify the failure boundary after a temporary snapshot file is allocated and SQLite opens its destination connection, but before online backup begins: applying the destination connection's `busy_timeout` fails and closing that connection fails as well.

## Contract

For both backup and restore:

1. `PersistentReplayReadinessError` reports the original SQLite configuration failure, preserving it as `__cause__`.
2. The destination connection close failure is recorded as a diagnostic note rather than replacing the primary error.
3. The outer snapshot routine attempts temporary-file and sidecar cleanup; no destination is published and no matching `.partial` artifact remains.
4. Source and, for restore, backup database artifacts remain unchanged.
5. Removing the injected failures allows a retry to publish and verify the expected destination.

## Scope

This part adds only a focused contract test and this operations note. It does not change production code, CLI output, or the published JSON Schema.

## Recovery

If equivalent failures happen in production, preserve the primary exception and inspect the filesystem for matching partial artifacts and SQLite sidecars before retrying. Confirm that the destination was not published before any retry.
