# Part 11-88 — Index Collision Post-Commit Reopened Writer Contract

## Purpose

Verify that duplicate required-index creation errors do not leave the database or SQLite write path unusable after the caller-owned outer transaction commits. A fresh writer connection must be able to begin a new transaction, perform valid transactional DDL, update `user_version`, and commit; the required index must remain canonical. Covers backup and restore destinations.

## Contract

- Begin an outer transaction, set a marker, and create a separate probe index. Within three savepoints, attempt to create the existing required index and verify each attempt fails with the same `already exists` error. Roll back each savepoint, preserving the caller transaction and canonical required index.
- Commit the outer transaction and close its connection. Verify its marker and valid probe index are visible through fresh connections.
- Open a new writer connection, begin an independent transaction, set a second marker, create and drop a temporary probe index, and commit. Reopen/read the database to verify the second marker persisted, the first committed probe index remains, the temporary probe index is absent, and the required index definition is canonical.
- Run the readiness API and `check --json` twice. Reports must remain identical, stderr must be empty, and checks must not change destination bytes or synthetic residual artifacts.
- Source/backup bytes and residual `.partial`, `-wal`, `-shm`, and `-journal` artifacts must remain unchanged.

This patch adds one test and one operations document. It does not change production code, CLI behavior, or the published JSON Schema.

## Validation

From `C:\projects\sh-3`, run:

```powershell
$env:SH3_PYTHON = "C:\anaconda3\envs\sh3-py312\python.exe"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-88-index-collision-post-commit-reopened-writer-contract\apply_patch.ps1"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-88-index-collision-post-commit-reopened-writer-contract\validate_patch.ps1"
```
