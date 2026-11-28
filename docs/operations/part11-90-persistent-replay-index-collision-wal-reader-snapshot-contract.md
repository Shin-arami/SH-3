# Part 11-90 — Index Collision WAL Reader Snapshot Contract

## Purpose

Verify that a deterministic read snapshot remains consistent while a separate SQLite writer commits schema changes after repeated required-index name collisions. The test explicitly uses WAL mode and covers both backup and restore destinations.

## Contract

- Prepare the destination in WAL journal mode and establish a read transaction by querying the claims table before a writer begins.
- In an independent writer connection, change `user_version` and create a probe index inside `BEGIN IMMEDIATE`.
- Attempt to create the required index with reversed key order three times under SAVEPOINTs. Every attempt must report `already exists`; rolling back each savepoint must preserve the writer's valid uncommitted changes and the canonical required-index definition.
- Commit the writer while the reader remains open. The reader must continue to observe its original `user_version`, required-index definition, and absence of the probe index. After ending and starting a new read transaction, that same connection must observe the writer's committed changes.
- Reopen fresh connections and verify the committed marker and probe index persist, while the required index remains owned by `sh3_replay_claims` with exactly `(state, lease_expires_at)`, non-unique and non-partial.
- Run the readiness API and `check --json` twice. Reports must be identical, stderr must be empty, and checks must not change database bytes, protected source/backup bytes, or synthetic residual `.partial`, `-wal`, `-shm`, and `-journal` artifacts.

This patch adds one contract test and one operations document. It does not change production code, CLI behavior, or the published JSON Schema.

## Validation

From `C:\projects\sh-3`, run:

```powershell
$env:SH3_PYTHON = "C:\anaconda3\envs\sh3-py312\python.exe"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-90-index-collision-wal-reader-snapshot-contract\apply_patch.ps1"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-90-index-collision-wal-reader-snapshot-contract\validate_patch.ps1"
```
