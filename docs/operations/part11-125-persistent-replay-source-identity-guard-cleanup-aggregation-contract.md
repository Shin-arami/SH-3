# Part 11-125 — Source Identity Guard and Cleanup Aggregation Contract

## Scope

This contract protects the source-identity guard error when cleanup of a verified temporary snapshot fails in more than one place. The test exercises both backup and restore flows without modifying production code or the published report schema.

## Injected scenario

After the SQLite online backup has completed into a temporary `.partial` file, the test injects a source-identity guard rejection at the `during snapshot creation` phase. It also creates representative temporary WAL and journal sidecars and injects `PermissionError` for WAL-sidecar and temporary-file deletion. This is deliberate fault injection of the identity guard rather than an attempt to replace an open SQLite database pathname, whose semantics differ across operating systems.

## Required invariants

- The original `PersistentReplayReadinessError` instance remains the raised exception.
- Cleanup attempts all sidecars and the temporary snapshot, even after the first `OSError`.
- Both cleanup failures appear in the exception's diagnostic note summary, including recovery guidance.
- No temporary snapshot is passed to the verification stage and no publication call occurs.
- The final destination remains absent and protected source/backup artifacts stay unchanged.
- After manually removing the injected orphan names, retrying to a fresh destination succeeds and the published destination remains absent.

## Validation

Run `validate_patch.ps1` from the repository root with the SH-3 Python 3.12+ interpreter. The script runs the focused contract, related snapshot/publication/cleanup/recovery tests, Ruff, Mypy, published JSON Schema syntax validation, the complete pytest suite, the deprecation-warning gate, whitespace checks, and `git diff --check`.

## Compatibility boundary

This patch adds a test and this operations document only. It does not alter `persistent_replay_ops.py`, CLI behavior, operational JSON output, or `persistent-replay-report-v1.schema.json`.
