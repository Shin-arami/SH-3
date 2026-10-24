# Part 11-86 — Index Collision Outer Rollback Contract

## Purpose

Verify that after a duplicate required-index creation fails repeatedly inside savepoints, the caller's full outer rollback removes unrelated transactional changes and restores the original persistent replay database state. Exercise both backup destinations and restore destinations.

## Contract

- Capture the canonical required-index definition, readiness report, claim count, `user_version`, source/backup bytes, and residual artifact contents before starting a write transaction.
- Begin an outer transaction, set a transaction-scoped `user_version` marker, and create a separate probe index as valid transactional DDL.
- Three times, attempt to create the existing required index inside a savepoint and confirm the same `already exists` error. Roll back each savepoint and verify the outer marker, probe index, claim count, and canonical index definition remain intact.
- Roll back the complete outer transaction. The probe index and outer marker must disappear, while the required index and original `user_version` remain.
- Verify `check_database` and two `check --json` invocations succeed with stable reports and empty stderr. Repeated checks must not change the destination bytes or residual artifact contents.
- The protected source/backup bytes and synthetic `.partial`, `-wal`, `-shm`, and `-journal` artifacts must remain unchanged.

This patch adds one test and one operations document. It does not change production code, CLI behavior, or the published JSON Schema.

## Validation

From `C:\projects\sh-3`, run:

```powershell
$env:SH3_PYTHON = "C:\anaconda3\envs\sh3-py312\python.exe"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-86-index-collision-outer-rollback-contract\apply_patch.ps1"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-86-index-collision-outer-rollback-contract\validate_patch.ps1"
```
