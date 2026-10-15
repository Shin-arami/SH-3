# Part 11-22 — Persistent Replay Operational Readiness

This runbook covers the SQLite-backed evidence and replay-claim database introduced in Part 11-17 and the lease/failure audits from Parts 11-18 through 11-21. It is intended for **single-host SQLite deployments**. It does not make arbitrary external side effects exactly-once and is not a substitute for a tested application-level disaster recovery plan.

## Safety rules

- Run the commands from the repository root with the supported Python 3.12 environment.
- The operational CLI's `check` command opens the database read-only. It runs SQLite `integrity_check` and `foreign_key_check`, checks required SH-3 tables/columns, verifies each evidence record with the same decoder used by the persistent store, checks row-key/document agreement, and validates replay-claim state invariants.
- Use the SQLite Online Backup API through the CLI. **Do not copy a live `.sqlite3` file by itself** while the database is in WAL mode: committed data may still be present in the `-wal` file. Do not manually copy only a `-wal` or `-shm` sidecar either.
- Backups contain application evidence and may contain operationally sensitive information. Protect them with appropriate filesystem ACLs, encryption at rest, controlled transfer, and retention policies.
- Backup and restore destinations must be new paths. The CLI refuses to overwrite existing files and publishes a verified snapshot without replacement. If the destination filesystem disallows hard links, the command fails safely; use a supported local filesystem destination.
- SQLite is supported here for a single host. Do not put this database on an arbitrary network share to coordinate multiple hosts.

## 1. Readiness check

Check the active database before maintenance and after an incident:

```powershell
py -3.12 -m infrastructure.security.persistent_replay_ops check --database "var\sh3\evidence.sqlite3"
```

A successful report includes SQLite version, journal mode, evidence count, replay-claim count, and expired-claim count. A failing check exits non-zero and must block a restore/cutover until the cause is understood.

`expired_claims > 0` is a recovery signal, not an instruction to delete or reset claims. Confirm whether an earlier worker can still perform external actions, then rely on the fencing generation and downstream idempotency contract when recovering. The CLI never modifies a claim to make the check pass.

The full `integrity_check` may take time on large databases. Run it as part of a planned operational check window and observe the configured SQLite busy timeout. An operational timeout is an incident to diagnose, not a reason to manually alter claim rows.

## 2. Create and verify a backup

Choose a new backup name and a protected local destination:

```powershell
py -3.12 -m infrastructure.security.persistent_replay_ops backup `
  --database "var\sh3\evidence.sqlite3" `
  --destination "backups\evidence-2026-10-16T0200.sqlite3"
```

The command validates the source, takes a transaction-consistent SQLite online backup, validates the snapshot, and only then publishes it to the destination. It refuses to overwrite a prior backup. The backup may use a different journal mode from the active database; check it with the same CLI rather than assuming the active database's `-wal` file is needed.

Verify an existing backup independently before relying on it:

```powershell
py -3.12 -m infrastructure.security.persistent_replay_ops check --database "backups\evidence-2026-10-16T0200.sqlite3"
```

For scheduled operations, retain command output and the backup path in the deployment's normal audit system. This utility does not implement backup rotation, encryption, remote upload, or retention deletion.

## 3. Restore to a new path

Do not restore over the active database. Stop or quiesce writers as part of the change window, restore into a **new** path, and verify it before switching application configuration:

```powershell
py -3.12 -m infrastructure.security.persistent_replay_ops restore `
  --backup "backups\evidence-2026-10-16T0200.sqlite3" `
  --destination "var\sh3\recovered\evidence.sqlite3"

py -3.12 -m infrastructure.security.persistent_replay_ops check --database "var\sh3\recovered\evidence.sqlite3"
```

Restore uses the SQLite backup API into a temporary file and refuses an existing destination. It does not stop SH-3 processes, change application configuration, swap directories, delete the original DB, or coordinate deployment cutover. Those actions require an operator-controlled maintenance procedure.

After a verified restore, start one SH-3 instance against the restored path first and run the application's replay/recovery acceptance tests before allowing normal traffic. Preserve the original database and backup until the recovery is accepted.

## 4. Failure response

| Signal | Response |
|---|---|
| `integrity_check` failure, missing tables, malformed evidence, or claim invariant failure | Stop cutover. Preserve the source file(s), logs, and backup. Diagnose and restore to a new path; never edit/delete rows manually as a shortcut. |
| `database is locked` / busy timeout | Identify long-lived readers/writers, confirm no backup or maintenance operation is holding a transaction, and retry only after bounded contention clears. Do not increase retry loops without a time budget. |
| Expired leases | Confirm whether an old worker may still be active. Fencing rejects stale claim finalization; downstream external actions still need their own idempotency or transaction boundary. |
| Backup/restore destination already exists | Select a new destination or archive the previous artifact under normal retention control. The utility intentionally does not overwrite files. |
| Backup API or validation failure | Treat the output as unusable. The temporary snapshot is removed on ordinary failures; inspect the directory for abandoned `.partial` files after an abrupt process or host failure. Retry to a new destination after checking storage health. |

## 5. Scope and limitations

- The readiness check validates SQLite structure, required schema, evidence integrity, evidence row-key agreement, and replay-claim state invariants. It does not prove business correctness of every evidence payload.
- A SQLite backup is a database-consistent snapshot; it does not capture external services, files, queues, or side effects that the application may have triggered.
- A replay claim cannot atomically commit an arbitrary external side effect. External operations must be idempotent or transactional with their evidence boundary.
- WAL improves local concurrency but does not turn SQLite into a multi-host coordination database. Use a storage adapter backed by a shared transactional database for a multi-host deployment.
- Run this utility with an account that has only the filesystem permissions needed for its task. Do not run the `restore` command against the active database path; the utility refuses to overwrite an existing file as an additional safeguard.
