# Part 11-129 — Online Snapshot Failure and Cleanup Aggregation Contract

This patch adds a contract test and an operations document only. It does not change production code, CLI behavior, or the published JSON Schema.

## Contract

The test injects failure in `_backup_to_temporary` after the temporary `.partial` path has been allocated. It independently injects failures when cleaning the temporary WAL sidecar and the temporary snapshot itself, while checking that the original online-snapshot exception remains primary and receives one diagnostic note reporting both cleanup failures.

The contract is exercised for both backup and restore destinations. It verifies that publication is not attempted, that input-database artifacts remain unchanged, that the other cleanup steps still execute, and that retry succeeds after the deliberately orphaned names are removed.

## Apply and validate

Extract the ZIP under `C:\temp`, open PowerShell in the SH-3 repository root (`C:\projects\sh-3`), and run:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-129-online-snapshot-failure-cleanup-aggregation-contract\apply_patch.ps1"
$env:SH3_PYTHON = "C:\anaconda3\envs\sh3-py312\python.exe"
powershell -ExecutionPolicy Bypass -File "C:\temp\part11-129-online-snapshot-failure-cleanup-aggregation-contract\validate_patch.ps1"
```

The validation script runs the focused contract test, related regressions, Ruff, Mypy, published schema syntax, the full pytest suite, the deprecation-warning gate, whitespace validation, and `git diff --check`.
