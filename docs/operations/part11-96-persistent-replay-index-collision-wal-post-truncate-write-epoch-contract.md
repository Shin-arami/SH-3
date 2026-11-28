# Part 11-96 — Index Collision WAL Post-TRUNCATE Write Epoch Contract

## Purpose

Verify that a completed WAL `TRUNCATE` checkpoint genuinely starts a fresh write epoch: a subsequent committed write generates new WAL frames, savepoint-isolated attempts to create the already-existing required replay-claim index remain harmless, and a later checkpoint can drain and truncate the new epoch independently of the previous one.

## Contract

- Exercise both a backup destination and a restore destination in WAL mode. Preserve the source and backup bytes and use distinct synthetic `.partial`, `-wal`, `-shm`, and `-journal` artifacts to prove readiness checks do not alter residual files.
- Commit the first write epoch after three attempts to create the required index under its existing name. Every attempt must produce the same `already exists` error; SAVEPOINT rollback must retain the epoch marker, probe index, and canonical required-index definition.
- Run `PRAGMA wal_checkpoint(TRUNCATE)` with no reader pinned. It must return `(0, 0, 0)`, proving the first WAL has been emptied before the next write epoch begins.
- Perform a second write epoch on the same connection, using a new marker and probe index. Repeat the same three collision attempts and verify that their errors are identical to those from the first epoch.
- A `PASSIVE` checkpoint after the second commit must complete every frame in the newly generated WAL. A subsequent `TRUNCATE` checkpoint must again return `(0, 0, 0)`.
- Confirm that both committed probe indexes remain, the required index is still owned by `sh3_replay_claims` with exactly `(state, lease_expires_at)` and is neither unique nor partial, and the second marker persists after reopening the database.
- Run the JSON readiness command twice. Reports must match, stderr must be empty, and checking must not change the destination bytes, protected source/backup, or synthetic residual artifacts.

This part adds one contract test and this operations document only. Production code, CLI behavior, and the published JSON Schema remain unchanged.

## Validation

From `C:\projects\sh-3`, run:

```powershell
$env:SH3_PYTHON = "C:\anaconda3\envs\sh3-py312\python.exe"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-96-wal-post-truncate-write-epoch-contract\apply_patch.ps1"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-96-wal-post-truncate-write-epoch-contract\validate_patch.ps1"
```
