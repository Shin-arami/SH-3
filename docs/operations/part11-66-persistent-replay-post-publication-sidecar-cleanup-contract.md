# Part 11-66 - Persistent Replay Post-Publication Sidecar Cleanup Contract

## Purpose

Part 11-65 made cleanup diagnostics actionable when snapshot publication has completed but deletion of a temporary artifact fails. This part covers the distinct WAL-sidecar failure shape: the WAL sidecar unlink fails, but cleanup must continue and still remove the temporary main snapshot link.

## Contract

A deterministic fault-injection test runs both `backup` and `restore` and enforces that:

- publication may already have completed when post-publication cleanup fails, so the CLI returns its established sanitized JSON error envelope and emits explicit verification-before-retry guidance on standard error;
- a failed `-wal` sidecar removal does not prevent attempts for `-shm`, `-journal`, or the temporary main snapshot;
- the deliberately residual `.partial-wal` artifact is observable to the test, while the temporary main `.partial` path is removed;
- the published destination remains readable and passes the existing database checker;
- source bytes are unchanged, source/destination absolute paths are not disclosed, and the published report schema remains unchanged.

## Compatibility and safety

This is a regression contract only. It adds no production code, CLI options, report fields, or published JSON Schema changes. The residual sidecar is removed by test cleanup after assertions.

## Operator recovery

If the operation reports a post-publication cleanup error, resolve filesystem or handle-access problems, inspect matching `.partial` artifacts and SQLite sidecars, verify the destination before retrying, and remember that destination publication may already have succeeded.

## Validation

Run `validate_patch.ps1` from the repository root with Python 3.12+. The script runs this contract, related Backup/Restore safety tests, Ruff, Mypy, published JSON Schema syntax validation, the full pytest suite, the deprecation-warning gate, and `git diff --check`.
