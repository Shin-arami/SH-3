# Part 11-93 — Index Collision WAL FULL Checkpoint Reader Contract

## Purpose

Verify that a `FULL` WAL checkpoint explicitly reports incomplete progress while an existing reader pins a pre-commit snapshot, and that the checkpoint completes after the reader releases that snapshot. The test exercises both backup and restore destinations while a writer commits a probe-index change after repeated required-index name collisions.

## Contract

- Establish a read transaction before the writer changes the destination in WAL mode. The reader must keep its original `user_version`, claim count, and canonical required-index definition.
- Commit a valid writer change after three savepoint-isolated attempts to create the required index under a colliding name. Each attempt must return the same `already exists` error and preserve the writer's valid in-transaction changes.
- Run `PRAGMA wal_checkpoint(FULL)` twice while the old reader remains open. With a zero-timeout checkpointer, each operation must return a three-column status with `busy = 1`, a non-zero WAL frame count, and fewer checkpointed frames than total frames. The second call must report the same incomplete progress.
- Confirm that the open reader still sees its pre-commit snapshot after both checkpoints. Once the reader ends that read transaction, a `FULL` checkpoint must return `busy = 0` and report all WAL frames checkpointed. A fresh read transaction must observe the writer's committed marker and probe index.
- Verify that the required index remains owned by `sh3_replay_claims`, with exactly `(state, lease_expires_at)`, non-unique and non-partial; the probe index and committed marker persist after reconnecting.
- Run the JSON readiness command twice. Reports must be identical, stderr must be empty, and checks must not change the destination, protected source/backup, or synthetic residual `.partial`, `-wal`, `-shm`, and `-journal` artifacts.

This part adds one contract test and this operations document only. Production code, CLI behavior, and the published JSON Schema are unchanged.

## Validation

From `C:\projects\sh-3`, run:

```powershell
$env:SH3_PYTHON = "C:\anaconda3\envs\sh3-py312\python.exe"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-93-wal-full-checkpoint-reader-contract\apply_patch.ps1"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-93-wal-full-checkpoint-reader-contract\validate_patch.ps1"
```
