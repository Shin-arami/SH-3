# Part 11-141 — Persistent Replay Snapshot Failure Operations Integration

## Purpose

Parts 11-132 through 11-140 established executable contracts for SQLite connection ownership, setup/close failures, source identity checks, temporary snapshot cleanup, publication safety, and retry behavior. This document integrates those tested outcomes into the operator workflow; it does not replace the individual contract tests and does not claim that all operating-system or storage failures are impossible.

## Contract-to-operations map

| Contract area | Verified behavior | Operator response |
|---|---|---|
| Part 11-132 and Part 11-133: destination connection open/configuration failure | The primary SQLite error is preserved; temporary state is cleaned where possible; source is not published or modified | Read the primary error and any cleanup details. Check the source, then inspect the destination directory if cleanup was reported incomplete. |
| Part 11-134 and Part 11-135: source/destination configuration and close failures | Connection cleanup continues, source ownership is respected, and cleanup errors do not replace the primary setup error | Preserve the diagnostic output. Do not infer successful publication from a successful online-backup call alone. |
| Part 11-136: post-backup close failure | A close failure prevents the temporary snapshot from being published | Verify the destination is absent and the input remains readable before retrying. |
| Part 11-137: source identity changed before publication | The operation fails closed and does not publish the temporary snapshot | Investigate path replacement, permissions, and concurrent maintenance. Re-run readiness checks after the source is stable. |
| Part 11-138: identity failure plus temporary cleanup failures | The identity error remains primary; cleanup failures are reported; retry remains possible after recovery | Inspect each named `.partial` or SQLite sidecar. Do not remove artifacts while a process may still own them. |
| Part 11-139 and Part 11-140: read-only source close failure, including concurrent temporary cleanup failure | A primary identity error is preserved; source-close and temporary-cleanup failures are diagnosed separately | Preserve logs and source/backup files, inspect the exact residue names, then validate before retrying. |

## Recovery decision sequence

1. **Preserve the inputs and evidence.** Do not edit the source SQLite database or the backup in place. Save the CLI output and any `DETAIL`/exception-note diagnostics with the incident record.
2. **Check the source.** Run the read-only readiness command against the exact source path. For restore, check the backup path. A failed check blocks recovery until the cause is understood.
3. **Classify the destination state before retrying.** A `FileExistsError` means a destination already exists or won a publication race: do not overwrite or delete it as generic cleanup. Verify it separately and select a new destination for a fresh backup/restore. If the report says `snapshot was published, but temporary cleanup was incomplete`, treat the destination as a possible successful publication and validate it before taking further action. For a failure before publication, expect no newly published destination; still verify rather than assume.
4. **Handle incomplete cleanup conservatively.** Look for the exact `.partial` path named in the diagnostic and its `-wal`, `-shm`, or `-journal` sidecars. First establish that no SH-3 process or SQLite connection is still using them. Preserve a copy of relevant evidence when the incident requires forensic retention. Remove only confirmed abandoned temporary pathnames/sidecars; never delete the source, a valid backup, or a destination that won a publication race. A temporary pathname may be a hard link to a valid published destination, so removing that temporary *name* is not permission to remove the destination.
5. **Retry once the cause is corrected.** Re-run readiness checks for the input and any existing destination. Use the same intended destination only if it is still absent and the previous failure was confirmed to have occurred before publication; otherwise choose a new unique destination. Keep retries bounded and observable.
6. **Record recovery evidence.** Retain the source check, destination check, command result, identified residue, cleanup action, and successful retry output. A passing automated test suite is not a substitute for a deployment-specific restore drill.

## Scope boundary

These procedures cover the local single-host SQLite backup/restore utility. They do not automate process shutdown, destination cutover, retention deletion, remote replication, backup encryption, or recovery of arbitrary external side effects. Those remain explicit deployment/operator responsibilities as described in Part 11-22.
