# Part 11-26 — Explicit Persistent Replay Database Provisioning

## Purpose

Provide a deliberate first-use command for creating the SQLite database used by `SQLiteEvidenceStore` and `SQLiteReplayClaimStore`. Normal runtime startup and maintenance remain separate operations. This command never chooses a default file path, never creates missing parent directories, and refuses every existing destination.

## Choose and verify the target path first

Set an explicit deployment-owned path. The example below is illustrative; replace it with the path selected for the target environment. `C:\SQLite` contains SQLite executables in the current development setup and must not be assumed to be the SH-3 database directory.

```powershell
$database = 'C:\Projects\SH-3-data\evidence.sqlite3'
$parent = Split-Path -Parent $database

if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
    throw "Create and verify the intended data directory first: $parent"
}
if (Test-Path -LiteralPath $database) {
    throw "Refusing to provision an existing target: $database"
}
```

Confirm the path is on a supported local filesystem, the service identity has only the required directory permissions, and the path is covered by the intended backup and retention policy. Do not use `.mypy_cache`, `.pytest_cache`, a source-controlled folder by default, or a guessed `var/` path for production data.

## One-time provisioning command

The command requires an explicit confirmation flag and uses exclusive file creation (`xb`) before initializing the evidence and replay-claim tables. It refuses an existing file without opening or changing it.

```powershell
py -3.12 -m infrastructure.security.persistent_replay_provision `
  --database $database `
  --confirm-first-use
```

A successful result includes `PROVISION: PASS`, the canonical path, SQLite version, journal mode, and zeroed evidence/claim counts. The parent directory must already exist. Do not run provisioning against a path that is intended to contain existing evidence.

Alternatively, set `SH3_PERSISTENT_REPLAY_DATABASE` and omit `--database`; the CLI resolves the path from that environment variable. An explicit `--database` value takes precedence.

## Verify and start

Always run the read-only readiness check separately after provisioning:

```powershell
py -3.12 -m infrastructure.security.persistent_replay_ops check `
  --database $database
```

For ordinary application startup, use `create_persistent_application_runtime()` without `create_if_missing=True`. The runtime must fail closed if the configured file is missing or invalid. Provisioning is a one-time operator action, not a startup fallback.

```powershell
$env:SH3_PERSISTENT_REPLAY_DATABASE = $database
```

The application owner must explicitly call `create_persistent_application_runtime()` after registering the domain operations used by that application. The repository does not declare a single business-specific production `main()` or choose its execution operation automatically.

## Failure and recovery behavior

- Missing confirmation: argument parsing fails before the database path is touched.
- Existing file or directory: command refuses the target; it does not truncate, reinitialize, or delete it.
- Missing parent directory: command fails without creating the directory.
- Initialization/verification failure after exclusive creation: the newly reserved file is left in place for inspection. Do not point an application at it. Preserve diagnostic output and quarantine or remove it only after verifying it is the newly created target and that no process has used it; cleanup is intentionally not automatic.
- Backup and restore: use `infrastructure.security.persistent_replay_ops`, which verifies the source and destination and refuses overwrites. Do not copy the main SQLite file alone while WAL is active.

## Acceptance checklist

1. Operator selects and reviews the explicit database path.
2. Parent directory exists and permissions/storage policy have been reviewed.
3. One-time provisioning uses `--confirm-first-use` and reports `PROVISION: PASS`.
4. Separate read-only `check` passes on the new database.
5. Normal startup uses the configured path with no automatic provisioning.
6. Backup/restore acceptance is performed on distinct paths before production recovery is signed off.
7. The actual live runtime path is recorded by the deployment owner; tests against temporary databases do not satisfy this sign-off.
