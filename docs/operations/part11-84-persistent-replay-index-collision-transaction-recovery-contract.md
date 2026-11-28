# Part 11-84 — Index Collision Transaction Recovery Contract

## Purpose

Verify that a duplicate required-index creation failure does not invalidate an explicit SQLite transaction or prevent later valid operations on the same connection. The contract exercises both a backup destination and a restore destination.

## Contract

- Begin an explicit write transaction and attempt to create the already-existing required index three times.
- Each attempt must raise SQLite's `already exists` error while the transaction remains active and the canonical index definition remains intact.
- After the failures, a separate temporary index can be created and dropped on the same connection; rolling back leaves no probe index behind.
- Closing the connection leaves the readiness check able to report success twice with stable JSON output and no stderr diagnostics.
- Protected source/backup files and synthetic `.partial`, `-wal`, `-shm`, and `-journal` artifacts remain unchanged.

The test performs the repair-like probe explicitly inside its own transaction and rolls it back. It does not modify production code, the CLI contract, or the published JSON Schema.

## Validation

From `C:\projects\sh-3`, run:

```powershell
$env:SH3_PYTHON = "C:\anaconda3\envs\sh3-py312\python.exe"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-84-index-collision-transaction-recovery-contract\apply_patch.ps1"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-84-index-collision-transaction-recovery-contract\validate_patch.ps1"
```
