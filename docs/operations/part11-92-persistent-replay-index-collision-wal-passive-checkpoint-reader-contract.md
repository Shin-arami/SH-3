# Part 11-92 — Index Collision WAL PASSIVE Checkpoint Reader Contract

## Purpose

Verify that a `PASSIVE` WAL checkpoint does not wait for a reader holding a pre-commit snapshot and does not misreport a partial checkpoint as a full checkpoint. The contract exercises both backup and restore destinations while a writer commits a probe-index change after repeated required-index name collisions.

## Contract

- Establish a read transaction before the writer changes the destination in WAL mode. The reader must keep its original `user_version`, claim count, and canonical required-index definition.
- Commit a valid writer change after three savepoint-isolated attempts to create the required index under a colliding name. Each attempt must return the same `already exists` error and preserve the writer's valid in-transaction changes.
- Run `PRAGMA wal_checkpoint(PASSIVE)` at least twice while the original reader remains open. Each operation must return promptly with a three-column status, report no blocking busy condition, and show that not all WAL frames have been checkpointed while the old snapshot is pinned.
- Confirm that the reader still sees its pre-commit snapshot after both checkpoints. Once it ends that read transaction, a `TRUNCATE` checkpoint must complete and a fresh read transaction must observe the writer's committed marker and probe index.
- Verify that the required index remains owned by `sh3_replay_claims`, with exactly `(state, lease_expires_at)`, non-unique and non-partial; the probe index and committed marker persist after reconnecting.
- Run the JSON readiness command twice. Reports must be identical, stderr must be empty, and checks must not change the destination, protected source/backup, or synthetic residual `.partial`, `-wal`, `-shm`, and `-journal` artifacts.

This part adds one contract test and this operations document only. Production code, CLI behavior, and the published JSON Schema are unchanged.

## Validation

From `C:\projects\sh-3`, run:

```powershell
$env:SH3_PYTHON = "C:\anaconda3\envs\sh3-py312\python.exe"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-92-wal-passive-checkpoint-reader-contract\apply_patch.ps1"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-92-wal-passive-checkpoint-reader-contract\validate_patch.ps1"
```
