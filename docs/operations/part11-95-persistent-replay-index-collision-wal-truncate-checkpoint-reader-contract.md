# Part 11-95 — Index Collision WAL TRUNCATE Checkpoint Reader Contract

## Purpose

Verify that a `TRUNCATE` WAL checkpoint cannot empty the WAL while an established reader pins an older snapshot, and that it completes once the reader releases that snapshot. The test covers backup and restore destinations while a writer commits valid state after repeated savepoint-isolated required-index name collisions.

## Contract

- Establish a read transaction before the writer changes the destination in WAL mode. The reader must continue to observe its original `user_version`, replay-claim count, and canonical required-index definition.
- Commit a valid writer-side marker and probe index after three attempts to create the required index under an already-used name. Each collision must produce the same `already exists` error while the SAVEPOINT rollback preserves the outer writer changes.
- Run `PRAGMA wal_checkpoint(TRUNCATE)` twice while the original reader transaction remains active. With a zero-timeout checkpointer, each attempt must return the three-column status with `busy = 1`, a non-zero WAL frame count, and fewer checkpointed frames than total frames. Repeated incomplete status must be stable.
- Verify that the held reader continues to see the pre-commit snapshot. After it ends the read transaction, a subsequent `TRUNCATE` checkpoint must return `busy = 0` and report zero log/checkpointed frames because SQLite has emptied the WAL. A new read transaction must observe the committed writer marker and probe index.
- Verify that the required index remains owned by `sh3_replay_claims`, uses exactly `(state, lease_expires_at)`, and is neither unique nor partial.
- Run the JSON readiness command twice. Reports must match, stderr must be empty, and checking must not alter the destination, protected source/backup, or synthetic `.partial`, `-wal`, `-shm`, and `-journal` artifacts.

This part adds one contract test and this operations document only. Production code, CLI behavior, and the published JSON Schema remain unchanged.

## Validation

From `C:\projects\sh-3`, run:

```powershell
$env:SH3_PYTHON = "C:\anaconda3\envs\sh3-py312\python.exe"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-95-wal-truncate-checkpoint-reader-contract\apply_patch.ps1"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-95-wal-truncate-checkpoint-reader-contract\validate_patch.ps1"
```
