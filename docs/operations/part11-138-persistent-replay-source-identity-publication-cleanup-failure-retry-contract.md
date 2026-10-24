# Part 11-138 — Source Identity Publication Guard, Cleanup Failure, and Retry Contract

## Scope

This contract verifies the source identity check immediately before snapshot publication. It injects source identity drift only after the temporary snapshot has passed verification, then injects failures while removing the temporary WAL sidecar and `.partial` snapshot. Backup and restore paths are both covered.

## Required behavior

- The pre-publication source identity failure remains the primary `PersistentReplayReadinessError`.
- Cleanup continues through every temporary sidecar and the temporary snapshot, even when two cleanup operations fail.
- The primary exception receives one diagnostic note reporting two incomplete cleanup operations and recovery guidance.
- No hard-link publication is attempted and the destination remains absent.
- The source database, and the backup input on restore, retain their captured contents.
- After the test removes the two injected residual artifacts, retrying to the same destination succeeds and creates no stale `.partial` artifacts.

## Change boundary

This part adds a contract test and this operations note only. Production code, CLI output, and the published JSON Schema remain unchanged.

## Validation

Run `validate_patch.ps1` from the repository root using the Python 3.12+ interpreter selected by `SH3_PYTHON`. The script runs the focused contract, related regressions, Ruff, Mypy, JSON Schema parsing, whitespace checks, the full pytest suite, the deprecation-warning gate, and `git diff --check`.
