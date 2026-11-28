# Part 11-135 — Source connection configuration and close-failure contract

## Purpose

Verify exception precedence and connection ownership when the internally owned read-only SQLite source connection fails while configuring `PRAGMA busy_timeout`, and optionally also fails while closing.

## Contract

The source configuration error must remain the primary `PersistentReplayReadinessError` cause. If the owned source connection's close operation also fails, that secondary failure is recorded in one diagnostic note without replacing the primary error. The source connection is closed exactly once, the destination connection is never opened, online backup never begins, and no temporary destination file is created. Source database bytes remain unchanged.

The success-close and failure-close variants ensure the path is tested both without diagnostic notes and with cleanup diagnostics.

## Scope

This part adds only a focused contract test and this operations note. Production code, CLI output, and the published JSON Schema remain unchanged.

## Recovery

Treat source connection setup as a prerequisite for opening the snapshot destination. Preserve its original error if setup fails, still attempt owned-resource cleanup, and attach cleanup failures as diagnostics instead of masking the primary cause.
