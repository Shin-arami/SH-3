# Part 11-65 - Persistent Replay Snapshot Cleanup Diagnostic Contract

## Purpose

Part 11-64 ensures every temporary snapshot cleanup target is attempted even when an individual unlink fails. A remaining operations gap is that cleanup errors were only attached as exception notes, which the CLI did not display. On a successful publication followed by a cleanup failure, the CLI could report an operating-system error without clearly stating that the destination had already been published.

## Contract

Deterministic tests exercise both `backup` and `restore` at two failure boundaries:

- A snapshot failure remains the primary error when deleting a WAL sidecar also fails. The CLI emits a sanitized cleanup diagnostic, continues all four cleanup attempts, leaves no main partial snapshot, and the test removes the deliberately residual sidecar after assertions.
- If publication succeeded but deletion of the private temporary main file fails, the operation returns the existing JSON error envelope with an `operating_system_error` classification. Standard error explicitly warns that publication occurred, recommends verifying the destination before retrying, and notes that temporary artifacts may need inspection after filesystem access is restored.

The diagnostics never print source or destination absolute paths. Each cleanup target is attempted, and the original primary exception is not replaced by a sidecar cleanup exception.

## Compatibility and safety

Production changes are limited to rendering safe exception notes on standard error and clarifying a post-publication cleanup failure. CLI arguments, JSON report keys, and the published JSON Schema remain unchanged. A post-publication cleanup failure is deliberately reported as an error with explicit recovery guidance rather than pretending the overall operation and cleanup both succeeded.

## Operator recovery

After resolving the filesystem permission, sharing, or handle issue, inspect the destination directory for matching `.partial` snapshot files and SQLite `-wal`, `-shm`, or `-journal` sidecars. Verify the published destination before retrying the backup/restore command, because publication may already have completed and destination creation is no-overwrite.

## Validation

Run `validate_patch.ps1`, inspect the production and test diffs, and run `git diff --cached --check` before committing. Validation includes the new cleanup diagnostic contract, related Part 11-55 through Part 11-64 Backup/Restore tests, Ruff, Mypy, JSON Schema syntax, the full pytest suite, and the deprecation-warning gate.
