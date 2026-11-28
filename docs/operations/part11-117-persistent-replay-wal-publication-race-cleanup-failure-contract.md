# Part 11-117 — WAL Snapshot Publication Race and Cleanup Failure Contract

## Purpose

Verify that a losing snapshot publisher preserves a valid competing destination when cleanup of its own temporary snapshot fails. The contract applies to both backup and restore destinations and complements the cleanup-failure and stale-partial publication contracts from Parts 11-114 through 11-116.

## Contract

- A competing publisher creates a valid destination from an independently verified snapshot immediately before the test operation attempts its own atomic hard-link publication.
- The losing operation raises `FileExistsError` and does not overwrite or remove the competing destination.
- Injected failure to unlink the losing operation's temporary snapshot is recorded as an exception note, while the original publication error remains the raised exception.
- The temporary snapshot created by the losing operation remains identifiable and readable until an explicit cleanup action removes it.
- The pre-existing stale `.partial` file and its `-wal`, `-shm`, and `-journal` sentinels remain byte-for-byte unchanged.
- The source, restore input where applicable, and independent competing winner remain byte-for-byte unchanged.
- Retrying against the occupied destination continues to refuse overwrite. After explicit removal of only the orphan temporary snapshot, retrying into a fresh destination succeeds.
- Both the competing winner and the newly published retry destination pass readiness checks. Repeated JSON checks return stable reports, exit code `0`, and empty standard error.

## Scope

This is a test-and-documentation-only contract. It does not change production code, CLI behavior, or the published JSON Schema. The tests inject the publication race and unlink failure deterministically; they do not rely on thread timing or operating-system scheduling.

## Validation

Run `validate_patch.ps1` from the repository root. The script runs the focused test, related snapshot/publication/recovery regressions, Ruff, Mypy, JSON Schema syntax validation, the full pytest suite, the deprecation-warning gate, whitespace checks, and `git diff --check`.
