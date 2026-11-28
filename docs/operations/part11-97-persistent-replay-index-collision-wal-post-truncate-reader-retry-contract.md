# Part 11-97 — WAL Post-TRUNCATE Reader Retry Contract

## Purpose

Verify that a reader pinned before a fresh WAL write epoch keeps its snapshot stable while repeated `TRUNCATE` checkpoint attempts are unable to finish. Once that reader releases its transaction, a new checkpoint must complete and the committed write epoch must remain valid.

## Contract

- Exercise both backup and restore destinations in WAL mode. Preserve source/backup bytes and synthetic `.partial`, `-wal`, `-shm`, and `-journal` artifacts.
- Open a read transaction and establish its snapshot before the write epoch. The reader must continue to observe the original `user_version`, the original claim count, and the canonical required index after the writer commits new changes.
- On a separate writer connection, commit a new `user_version` marker and a probe index after three SAVEPOINT-isolated attempts to create the already-existing required index. All attempts must return the same `already exists` error; rolling back each SAVEPOINT must restore the epoch marker and preserve the canonical required index.
- While the old reader is still active, run `PRAGMA wal_checkpoint(TRUNCATE)` twice. Each attempt must report `busy = 1` with WAL frames remaining uncheckpointed. The two results must be stable, and neither attempt may invalidate the reader's snapshot.
- Release and close the reader, then rerun `TRUNCATE`. It must return `(0, 0, 0)`; if the WAL file remains present while the connection is open, its size must be zero.
- Verify the committed marker and probe index persist, and that the required index still belongs to `sh3_replay_claims` with exactly `(state, lease_expires_at)` and neither unique nor partial attributes.
- Run the JSON readiness command twice. Reports must match, stderr must be empty, and readiness checking must not change the destination bytes, protected source/backup, or synthetic residual artifacts.

This part adds one contract test and this operations document only. Production code, CLI behavior, and the published JSON Schema remain unchanged.

## Validation

From `C:\projects\sh-3`, run:

```powershell
$env:SH3_PYTHON = "C:\anaconda3\envs\sh3-py312\python.exe"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-97-wal-post-truncate-reader-retry-contract\apply_patch.ps1"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-97-wal-post-truncate-reader-retry-contract\validate_patch.ps1"
```
