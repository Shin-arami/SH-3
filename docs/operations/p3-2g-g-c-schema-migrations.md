# P3-2G G-C — Persistent Replay Database Schema Lifecycle

## Scope

This change introduces the dedicated `sh3_schema_metadata.schema_version` value as the authoritative SH-3 persistent replay schema version. `PRAGMA user_version` is deliberately preserved as an independent SQLite application marker because existing snapshot/restore contracts depend on its exact preservation. Version 1 describes the complete five-table persistent replay schema: evidence, replay claims, stage executions, operations, and operation plans.

The readiness CLI JSON contract remains unchanged: its `schema_version` field identifies the report format. The database schema version is intentionally not added to the readiness JSON payload; migration output reports source and target database schema versions.

## Version policy

- A newly provisioned, empty database is initialized at database schema version 1.
- Existing pre-versioned databases are treated as version 0.
- The only migration supported by this release is 0 → 1.
- A version-0 database is accepted for migration only when the existing tables and rows pass the read-only legacy structural, foreign-key, and integrity checks.
- Unknown, negative, or future versions fail closed. No downgrade or speculative repair is attempted.

## Migration procedure

Run from the repository root using Python 3.12 or newer:

```powershell
py -3.12 -m infrastructure.security.persistent_replay_migrate `
  --database "C:\data\sh3-replay.sqlite3" `
  --backup "C:\data\backups\sh3-replay-pre-v1.sqlite3" `
  --confirm-migration
```

The backup destination must not already exist. The migration acquires a SQLite write reservation, validates the version-0 database, creates and verifies an online backup, and then performs missing-table/index creation plus insertion of `sh3_schema_metadata.schema_version = 1` in one transaction. The migration does not rewrite or delete existing Evidence, Claim, Stage, Operation, or Action Plan rows.

If DDL fails before commit, SQLite rolls the schema changes and schema metadata update back together; the pre-existing `PRAGMA user_version` value remains untouched. The verified backup is retained for operator recovery. A second invocation on a database already at version 1 is a no-op and does not overwrite or recreate the backup.

## Startup and readiness behavior

`check_database()` remains read-only and requires the current database schema version by default. The Runtime Factory validates the existing database before constructing stores; an unversioned database is rejected with a migration-required error rather than being upgraded during startup. Store constructors initialize a truly new/empty SQLite file only; an existing version-0 database containing SH-3 tables is not repaired by constructors.

The explicit first-use Provisioner creates a new database and verifies that it reaches version 1. Runtime creation of a missing database remains opt-in through the existing `create_if_missing=True` pathway.

## Action Plan compatibility is separate

Database schema version 1 does not convert legacy Action Plan version-1 rows into Action Plan version 2. G-B's Action contract checks remain in force. A DB migration updates the SQLite table layout only; it does not fabricate implementation or rollback compatibility metadata for historical Action Plans.

## Recovery

A pre-migration backup is a version-0 database. It is not runtime-ready until migrated. A transaction failure leaves the source at version 0 and keeps the backup. If a post-commit operational check fails, stop application writers and preserve both files. Restore the verified pre-migration backup to a separate path with the explicit recovery opt-in `restore_database(backup_path, recovery_path, allow_unversioned_schema=True)`. This opt-in only permits verification and restoration of the version-0 snapshot; it does not make that copy runtime-ready. Run the explicit 0 → 1 migration against the restored copy, using a new, non-existing backup path, before starting Runtime. Never overwrite the original or delete historical rows to bypass a readiness failure.

## Verification

Tests cover version-0 migration, existing evidence/claim row preservation, backup publication, migration failure rollback, future-version refusal, read-only readiness, Runtime refusal before migration, first-use version initialization, and idempotent re-entry after migration.
