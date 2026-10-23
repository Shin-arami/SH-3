# Part 11-109 — WAL Backup Snapshot Checkpoint Isolation Contract

## Purpose

Verify that a published online-backup snapshot remains an immutable point-in-time artifact while its WAL source continues through committed write epochs and different checkpoint modes. Exercise both a backup destination and a restore destination without changing production code, CLI behavior, or the published JSON Schema.

## Contract

- Create a verified snapshot from an initialized SQLite database in WAL mode.
- In the backup scenario, continue writing to the source after publishing the snapshot. In the restore scenario, restore the snapshot to a separate WAL-mode destination and continue writing to that destination.
- Execute two committed write epochs. Each epoch attempts to create the required replay-claim index three times under a savepoint; each duplicate-name failure must be stable, rollback must be scoped to the savepoint, and the canonical index must remain intact.
- After each epoch, run checkpoint modes in distinct orders: `PASSIVE`, `FULL`, `RESTART`, `TRUNCATE`; then `TRUNCATE`, `RESTART`, `FULL`, `PASSIVE`.
- Checkpointing and later writes must not change the published snapshot bytes, protected source/backup bytes, or seeded residual `.partial` artifacts.
- Restoring the published snapshot after the source has moved through both write epochs must reproduce the original `user_version`, replay counts, and canonical index, and must not include the test-only indexes.
- Repeated CLI `check --json` runs on the active database must produce the same successful report with empty stderr.

## Validation

Run `validate_patch.ps1` from the repository root with `SH3_PYTHON` set to the Python 3.12+ interpreter. The script runs the focused contract, related WAL / replay regressions, Ruff, Mypy, schema syntax, the full pytest suite, the deprecation-warning gate, whitespace validation, and `git diff --check`.

## Change boundary

Only this operations document and the contract test are added. Production Python, CLI options, JSON report fields, and the published JSON Schema remain unchanged.
