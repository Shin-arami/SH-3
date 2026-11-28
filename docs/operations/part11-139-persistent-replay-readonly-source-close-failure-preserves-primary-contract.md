# Part 11-139 — Read-Only Source Connection Close Failure Preserves Primary Error

## Scope

This contract injects a source identity change at the final pre-publication guard and then makes the owned read-only source connection's `close()` raise. It covers both backup and restore inputs.

## Required behavior

- The pre-publication `PersistentReplayReadinessError` remains the primary exception.
- The read-only source connection close failure is retained as one diagnostic note, not substituted for the primary identity error.
- The source connection is closed exactly once even though its close operation reports an error.
- No publication is attempted; the destination remains absent and the temporary `.partial` artifact is cleaned.
- Source database contents and, for restore, backup-input contents remain unchanged.
- After the injected drift and close fault are removed, retrying to the same destination succeeds.

## Change boundary

This part updates the `_readonly_connection` cleanup path so a close error cannot mask an exception already active in the managed operation. A contract test and this operations note are added. CLI output and the published JSON Schema are unchanged.

## Validation

Run `validate_patch.ps1` from the repository root with `SH3_PYTHON` set to the Python 3.12+ interpreter. The script executes the focused contract, related regressions, Ruff, Mypy, JSON Schema parsing, whitespace checks, full pytest, the deprecation-warning gate, and `git diff --check`.
