# Part 11-108 — WAL Backup/Restore Under an Uncommitted Writer Contract

## Purpose

Verify that the persistent replay online backup and restore CLI operations create a verified snapshot of the last committed SQLite state when a separate writer connection holds an uncommitted WAL transaction. Snapshot creation must neither commit the writer's changes nor mutate the source database or its WAL as a side effect of observation.

## Contract

- Cover both `backup-destination` and `restore-destination` flows.
- Put the operation input into WAL mode and hold an explicit `BEGIN IMMEDIATE` writer transaction with an uncommitted `user_version` update and a temporary probe index.
- Attempt creation of the required `sh3_replay_claims_state_idx` three times inside SAVEPOINT scopes; each attempt must fail with the same `already exists` error, and rolling back the SAVEPOINT must preserve the outer transaction and canonical required-index definition.
- Invoke the actual `backup --json` or `restore --json` CLI path in a separate Python process while the writer is still open.
- Confirm the resulting snapshot reports a healthy database containing only the input's committed state; it must not contain the uncommitted probe index or the uncommitted `user_version` value.
- Confirm the input database and WAL bytes remain unchanged while snapshot creation runs, and confirm the writer still owns its transaction afterwards.
- Commit the writer after snapshot publication and prove the published snapshot remains unchanged and valid.
- Ensure JSON output is deterministic in shape, stderr is empty on success, and synthetic `.partial` / sidecar artifacts remain byte-for-byte unchanged.
- Keep changes test-only: production code, CLI implementation, and the published JSON Schema are unchanged.

## Validation

Run `validate_patch.ps1` from the repository root with `SH3_PYTHON` set to the Python 3.12+ interpreter. The script runs the focused contract, related WAL/index/recovery/CLI regressions, Ruff, Mypy, published JSON Schema parsing, the full pytest suite, the deprecation-warning gate, whitespace checks, and `git diff --check`.
