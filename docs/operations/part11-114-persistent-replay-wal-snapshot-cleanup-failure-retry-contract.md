# Part 11-114 — WAL Snapshot Cleanup Failure and Retry Contract

## Purpose

Verify that a one-shot failure while deleting a verified temporary SQLite snapshot is reported without hiding the primary publication failure, while the uncommitted destination remains unpublished and protected source databases are preserved. After the filesystem fault is removed and the leftover temporary snapshot is explicitly cleaned up, a retry to the same destination must succeed.

## Contract

- Exercise both `backup-destination` and `restore-destination` scenarios.
- Inject one `os.link` publication failure and one `Path.unlink` failure targeting only the generated `.partial` snapshot. Preserve ordinary cleanup behavior for sidecars and sentinel artifacts.
- The raised `PersistentReplayReadinessError` must retain the publication error and include a diagnostic note indicating that temporary snapshot cleanup was incomplete.
- The destination must not be published after the failed operation. The generated temporary file may remain when cleanup itself fails; the test verifies its SQLite file signature and explicitly removes it after removing the injected fault.
- Test-created `.partial`, `-wal`, `-shm`, and `-journal` sentinel artifacts must remain byte-identical.
- Source and (for restore) input-backup databases, including existing sidecars, must remain byte-identical.
- A subsequent operation to the same destination must publish a valid database with the canonical `sh3_replay_claims_state_idx` definition and expected probe index.
- Repeated subprocess `check --json` calls must return identical successful reports with exit code 0 and empty stderr.

## Scope

This is a test-and-documentation-only contract. Production code, CLI behavior, and the published JSON Schema are unchanged.

## Validation

Run `validate_patch.ps1` from the repository root using the project's Python 3.12+ interpreter. The gate includes the focused contract, related WAL/snapshot/recovery/JSON CLI regressions, Ruff, Mypy, published-schema syntax, the full pytest suite, the deprecation-warning gate, whitespace checks, and `git diff --check`.
