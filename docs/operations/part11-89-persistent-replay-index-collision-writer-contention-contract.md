# Part 11-89 — Index Collision Writer Contention Contract

## Purpose

Verify deterministic handling of overlapping SQLite writer operations after a required-index name collision. One connection holds a write transaction while another connection attempts to acquire the writer lock. Once the first transaction commits, the same second connection must recover, observe the committed schema, isolate repeated duplicate-index failures with savepoints, and successfully commit its own valid changes. Covers backup and restore destinations.

## Contract

- Start two independent SQLite writer connections with a zero lock timeout so the locking boundary is deterministic and does not depend on thread scheduling.
- Let the first connection begin an immediate transaction, update `user_version`, and create a probe index. The second connection's concurrent `BEGIN IMMEDIATE` must fail as locked/busy without entering a transaction or mutating the database.
- Commit the first writer. Reuse the same second connection, begin a transaction, and attempt to create the already-existing required index three times within savepoints. Every attempt must raise the same `already exists` error; rolling back each savepoint must preserve the second transaction, the first writer's committed work, and the canonical required-index definition.
- Commit valid work from the second connection and verify through fresh read connections that both writers' committed markers and probe indexes remain present. The required index must still belong to `sh3_replay_claims` and contain exactly `(state, lease_expires_at)` in order, without UNIQUE or partial-index properties.
- Run the readiness API and `check --json` twice. Reports must be identical, stderr must be empty, and checks must not change database bytes or synthetic residual artifacts.
- Source/backup bytes and residual `.partial`, `-wal`, `-shm`, and `-journal` artifacts must remain unchanged.

This patch adds one contract test and one operations document. It does not change production code, CLI behavior, or the published JSON Schema.

## Validation

From `C:\projects\sh-3`, run:

```powershell
$env:SH3_PYTHON = "C:\anaconda3\envs\sh3-py312\python.exe"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-89-index-collision-writer-contention-contract\apply_patch.ps1"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-89-index-collision-writer-contention-contract\validate_patch.ps1"
```
