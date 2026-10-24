# Part 11-85 — Index Collision Savepoint Isolation Contract

## Purpose

Verify that a failed duplicate-index creation is isolated to an explicit SQLite savepoint and does not erase the caller's earlier transaction state. Exercise both backup destinations and restore destinations.

## Contract

- Start an outer write transaction and record a transaction-scoped `PRAGMA user_version` marker.
- Repeat three times: create a savepoint, change the marker inside the savepoint, attempt to create the already-existing required index, and roll back to the savepoint.
- Each index creation must raise the same `already exists` error. Rolling back the savepoint must restore the outer marker, keep the outer transaction active, and preserve the canonical index definition and claim count.
- Valid index create/drop statements must still succeed in the outer transaction after each failed collision attempt.
- Restore the original `user_version` before committing. A subsequent readiness check must pass twice with stable JSON and empty stderr.
- Protected source/backup files and synthetic `.partial`, `-wal`, `-shm`, and `-journal` artifacts must remain unchanged.

This patch adds one test and one operations document. It does not change production code, CLI behavior, or the published JSON Schema.

## Validation

From `C:\projects\sh-3`, run:

```powershell
$env:SH3_PYTHON = "C:\anaconda3\envs\sh3-py312\python.exe"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-85-index-collision-savepoint-isolation-contract\apply_patch.ps1"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-85-index-collision-savepoint-isolation-contract\validate_patch.ps1"
```
