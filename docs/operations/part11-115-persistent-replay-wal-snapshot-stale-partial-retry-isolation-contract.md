# Part 11-115 — WAL Snapshot Stale Partial Retry Isolation Contract

## Purpose

Verify that a retry after a failed snapshot publication and failed cleanup creates a fresh temporary snapshot without adopting, overwriting, or deleting a stale `.partial` left by the earlier attempt. The successful retry must publish a verified destination while preserving protected sources and pre-existing residual artifacts.

## Contract

- Exercise both `backup-destination` and `restore-destination` scenarios.
- Inject one publication (`os.link`) failure and one cleanup (`Path.unlink`) failure, leaving a verified SQLite temporary snapshot unpublished.
- Confirm that the primary publication error remains visible and the cleanup-incomplete diagnostic note is preserved.
- Retry to the same destination while the orphaned partial still exists. The retry must succeed using its newly allocated temporary file.
- The older orphaned partial must remain byte-identical and must not be reused, overwritten, or silently removed by the retry.
- Source and (for restore) input-backup databases and their existing sidecars must remain byte-identical.
- Test-created `.partial`, `-wal`, `-shm`, and `-journal` sentinel artifacts must remain byte-identical throughout the failed attempt and successful retry.
- The published destination must pass readiness checks and preserve the canonical `sh3_replay_claims_state_idx` definition and expected probe index.
- Repeated subprocess `check --json` calls must return identical successful reports, exit code 0, and empty stderr.
- Only after the successful retry is verified, explicitly remove the stale partial and verify cleanup does not alter the destination or protected files.

## Scope

This is a test-and-documentation-only contract. Production code, CLI behavior, and the published JSON Schema are unchanged.

## Validation

Run `validate_patch.ps1` from the repository root using the project's Python 3.12+ interpreter. The gate includes the focused contract, related WAL/snapshot/recovery/JSON CLI regressions, Ruff, Mypy, published-schema syntax, the full pytest suite, the deprecation-warning gate, whitespace checks, and `git diff --check`.
