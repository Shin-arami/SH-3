# Part 11-91 — Index Collision WAL Checkpoint Reader Contract

## Purpose

Verify that a WAL `TRUNCATE` checkpoint is safely deferred while a reader holds an older SQLite snapshot and completes after that reader releases the snapshot. The contract runs against both backup and restore destinations and preserves the required replay-claim index throughout repeated name-collision failures.

## Contract

- Prepare the destination in WAL journal mode and establish a read transaction before the writer modifies the WAL.
- In a separate writer connection, change `user_version` and create a probe index inside `BEGIN IMMEDIATE`.
- Attempt to create the required index under three SAVEPOINTs. Each attempt must return `already exists`; rollback to the SAVEPOINT must preserve the outer transaction, the writer's valid changes, and the canonical required-index definition.
- Commit the writer while the older reader remains open. A `PRAGMA wal_checkpoint(TRUNCATE)` must report that it cannot fully complete while the reader is holding its snapshot, and the reader must continue to observe the pre-commit state.
- Release the reader snapshot and rerun the checkpoint. It must complete without a busy result and report a fully truncated WAL. A new read transaction must then observe the committed writer marker and probe index while the required index still has exactly `(state, lease_expires_at)`, is owned by `sh3_replay_claims`, and is neither unique nor partial.
- Run the readiness API and `check --json` twice. The reports must be identical, stderr must be empty, protected source/backup bytes must remain unchanged, and synthetic residual `.partial`, `-wal`, `-shm`, and `-journal` artifacts must remain byte-stable.

This patch adds one contract test and one operations document. It does not change production code, CLI behavior, or the published JSON Schema.

## Validation

From `C:\projects\sh-3`, run:

```powershell
$env:SH3_PYTHON = "C:\anaconda3\envs\sh3-py312\python.exe"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-91-index-collision-wal-checkpoint-reader-contract\apply_patch.ps1"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-91-index-collision-wal-checkpoint-reader-contract\validate_patch.ps1"
```
