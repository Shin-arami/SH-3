# Part 11-23 — Runtime Store Wiring & Database Lifecycle Audit

## Purpose

Use one explicit configuration boundary for the SQLite evidence store and replay-claim store. Fail startup instead of silently substituting an in-memory store or creating a new empty database when an existing database path was misspelled.

## Configuration

The runtime path is read from `SH3_PERSISTENT_REPLAY_DATABASE`. An explicit `database_path` argument overrides that environment variable. Resolution is side-effect free; it does not create directories or files.

PowerShell example:

```powershell
$env:SH3_PERSISTENT_REPLAY_DATABASE = "D:\SH-3\data\evidence.sqlite3"
```

Inspect an existing database without opening it through the application adapters:

```powershell
py -3.12 -m infrastructure.security.persistent_replay_ops check --database "$env:SH3_PERSISTENT_REPLAY_DATABASE"
```

## Runtime wiring

At normal application startup, require that the configured database already exists and passes the read-only readiness checks. Pass the same bundle's two stores to the kernel:

```python
from infrastructure.security.persistent_replay_runtime import (
    create_persistent_replay_stores,
)
from kernel.core import SH3Kernel

stores = create_persistent_replay_stores()
kernel = SH3Kernel(
    evidence_store=stores.evidence_store,
    replay_claim_store=stores.replay_claim_store,
)
```

`create_persistent_replay_stores()` validates an existing database before opening either adapter, then verifies the initialized state. It exposes the resolved path and ensures both adapters target the same file. Store operations open and close their own SQLite connections; the bundle owns no long-lived connection and therefore has no `close()` requirement.

## First-time provisioning

A missing database is an error by default. This protects production restarts from a typo silently creating a new, empty evidence history. For deliberate first-time setup only, run:

```python
from infrastructure.security.persistent_replay_runtime import (
    create_persistent_replay_stores,
)

stores = create_persistent_replay_stores(create_if_missing=True)
print(stores.database_path)
```

This path initializes both SH-3 tables in the same SQLite file. After provisioning, ordinary runtime startup should omit `create_if_missing=True`. Verify the database with the operational CLI before enabling traffic.

## Backup and restore lifecycle

Back up and restore only a path reported by the runtime configuration or deployment configuration. Do not assume a repository-relative `var/` path, and do not use `.mypy_cache` databases. The operational CLI takes an explicit path and must be run against the exact database used by the application:

```powershell
py -3.12 -m infrastructure.security.persistent_replay_ops backup `
  --database "$env:SH3_PERSISTENT_REPLAY_DATABASE" `
  --destination "D:\SH-3\backups\evidence-before-upgrade.sqlite3"
```

Verify the backup before treating it as a recovery point:

```powershell
py -3.12 -m infrastructure.security.persistent_replay_ops check `
  --database "D:\SH-3\backups\evidence-before-upgrade.sqlite3"
```

Restore to a new path; the CLI intentionally refuses to overwrite an existing file:

```powershell
py -3.12 -m infrastructure.security.persistent_replay_ops restore `
  --backup "D:\SH-3\backups\evidence-before-upgrade.sqlite3" `
  --destination "D:\SH-3\recovery\evidence.sqlite3"
```

After restore, run `check` on the destination and configure the application to use that exact path only after verifying evidence and claim counts. Keep the original database and backup unchanged until recovery has been accepted.

## Lifecycle and failure behavior

- Missing configuration: fail before opening a store.
- Missing database during normal startup: fail without creating a parent directory or database file.
- First-time creation: requires explicit `create_if_missing=True`.
- Existing malformed, unrelated, or inconsistent database: readiness checks fail before adapters are opened; no automatic schema repair is attempted by this wiring factory.
- Path mismatch between the evidence and claim stores: bundle construction fails.
- SQLite busy/locked error: surface the failure to the caller; retry only at an orchestration boundary with bounded backoff and idempotent semantics.
- Startup interruption during deliberate first-time provisioning: initialization can leave an incomplete new file if the process stops mid-setup. Keep the application offline, run the read-only readiness check, and only remove the incomplete file after verifying it is the newly provisioned target and no process uses it. The factory never deletes database files.
- Backup source: use SQLite Online Backup through `persistent_replay_ops`, not a manual copy of only the main file while WAL is in use.
- Exactly-once external effects: not guaranteed by a durable claim alone. Side-effecting downstream operations still need idempotency keys or a transaction boundary.

## Acceptance checklist

1. `SH3_PERSISTENT_REPLAY_DATABASE` points to the deployment's actual database.
2. `check` reports `integrity_check=ok` and valid SH-3 evidence/claim schemas.
3. Application startup receives the two stores from one `PersistentReplayStores` bundle.
4. Startup does not create a new database when the configured path is missing.
5. A deliberate new database is provisioned only in a controlled first-run step.
6. Backup and restore are tested to separate paths and both are verified with `check`.
7. Restored evidence and replay-claim state are checked before switching runtime traffic.
