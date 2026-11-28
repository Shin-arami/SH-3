# Part 11-87 — Index Collision Outer Commit Contract

## Purpose

Verify that repeated duplicate-index creation failures isolated by savepoints do not poison a caller-owned outer transaction: valid outer work can still be committed, while the failed collision attempts contribute no schema changes. Exercise both backup destinations and restore destinations.

## Contract

- Capture the canonical required-index definition, readiness report, claim count, original `user_version`, source/backup bytes, and residual artifact contents before starting a write transaction.
- Begin an outer transaction, set a transaction-scoped `user_version` marker, and create a separate probe index as valid transactional DDL.
- Three times, attempt to create the existing required index inside a savepoint and confirm the same `already exists` error. Roll back each savepoint and verify that the outer marker, probe index, claim count, and canonical index definition remain intact.
- Commit the complete outer transaction. The probe index and outer marker must persist; the failed duplicate-index attempts must not replace or alter the canonical required index.
- Verify `check_database` and two `check --json` invocations succeed with stable reports and empty stderr. Repeated checks must not change destination bytes, the committed marker/index, or residual artifact contents.
- The protected source/backup bytes and synthetic `.partial`, `-wal`, `-shm`, and `-journal` artifacts must remain unchanged.

This patch adds one test and one operations document. It does not change production code, CLI behavior, or the published JSON Schema.

## Validation

From `C:\projects\sh-3`, run:

```powershell
$env:SH3_PYTHON = "C:\anaconda3\envs\sh3-py312\python.exe"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-87-index-collision-outer-commit-contract\apply_patch.ps1"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-87-index-collision-outer-commit-contract\validate_patch.ps1"
```
