# Part 11-130 — Connection-close failure preserves the primary snapshot error

## Purpose

Define the cleanup contract for SQLite connections opened by `_backup_to_temporary`.

## Contract

- The destination connection is closed even when online backup raises.
- If this function owns the source connection, its close is attempted even if destination close fails.
- A primary online-backup failure remains the raised `PersistentReplayReadinessError`; close failures are appended as one diagnostic note and cannot replace the primary exception or its cause.
- If online backup itself succeeds but connection close fails, the function fails closed with a `PersistentReplayReadinessError` that reports the number and details of close failures. Both closes are attempted.
- Connection cleanup failures are never silently dropped.

## Scope

This part changes `infrastructure/security/persistent_replay_ops.py` and adds two focused contract tests. It does not change CLI output schemas or `docs/operations/schemas/persistent-replay-report-v1.schema.json`.

## Validation

Run `validate_patch.ps1` from the repository root with the project's Python 3.12+ interpreter. The script runs focused tests, related snapshot/publication/cleanup regressions, Ruff, Mypy, schema syntax, the full pytest suite, the deprecation-warning gate, whitespace validation, and `git diff --check`.
