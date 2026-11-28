# Part 11-113 — WAL Snapshot Publication Failure Cleanup and Retry Contract

## Scope

This contract covers a transient failure at the atomic publication boundary used by persistent replay online backup and restore. It is test-only: production code, command-line behavior, and the published JSON Schema are unchanged.

## Required behavior

For both backup and restore destinations:

1. Build and verify an online SQLite snapshot from a valid WAL-mode source.
2. Inject one `os.link` publication failure after the temporary snapshot has been verified.
3. Require the operation to fail with `PersistentReplayReadinessError`, leave the requested destination absent, and remove only its own temporary snapshot and sidecars.
4. Preserve pre-existing `.partial`, `-wal`, `-shm`, and `-journal` sentinel artifacts byte-for-byte.
5. Preserve the source and (for restore) input backup database and any active SQLite sidecars byte-for-byte.
6. Retry the same operation to the same destination without injection and require a valid snapshot with the canonical `sh3_replay_claims_state_idx` and the expected user version.
7. Run JSON Readiness Check twice in subprocesses. Both runs must return the same successful report, use exit code zero, produce no stderr output, and leave database artifacts unchanged.

## Failure boundary

The injected failure represents a transient filesystem publication failure, not an invalid database. The contract distinguishes operation failure from partial publication: a failed link must not leave a visible destination, and retrying must not require an operator to delete generated temporary artifacts manually.

## Validation

`validate_patch.ps1` executes this contract, related snapshot/restore and WAL regressions, Ruff, Mypy, published JSON Schema parsing, the complete pytest suite, the deprecation-warning gate, whitespace validation, and `git diff --check`.
