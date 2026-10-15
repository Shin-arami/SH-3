# Part 11-21 — Persistent Replay Failure Matrix

**Baseline:** `efeb8e015adf926908a391cf9a5e0c2d4ba19893` (`v2.2-development`)

This document records expected behavior for the SQLite-backed evidence and replay-claim boundary. It complements the executable tests added in Part 11-21; it does not claim that arbitrary external side effects are exactly-once.

## Failure matrix

| Failure or race | Expected behavior | Recovery/acceptance evidence |
|---|---|---|
| Two writers register different payloads under one evidence ID | At most one canonical record is persisted; all conflicting writers fail with an identity conflict | The reopened store returns one verifiable record and row count remains one |
| Evidence row integrity metadata is modified independently of the serialized record | Read fails closed with `PersistentEvidenceIntegrityError`; the store does not silently rewrite the record | Explicit row-integrity tampering test |
| SQLite writer lock blocks evidence registration past the configured timeout | The operation raises `sqlite3.OperationalError`; no partial evidence row appears | After releasing the lock, a retry persists exactly one record |
| SQLite writer lock blocks claim creation | The operation raises `sqlite3.OperationalError`; no partial claim is inserted or attempt counter incremented | After releasing the lock, a retry creates generation 1 / attempt 1 |
| SQLite writer lock blocks claim completion | The original claimed owner, generation, and lease remain intact | After releasing the lock, the same owner can complete successfully |
| A lease expires and another owner acquires a newer generation | The previous owner cannot finalize the claim | Covered by Part 11-18 / Part 11-19 lease and fencing tests |
| Terminal evidence is durable but claim completion is interrupted | Recreated Kernel reconciles the claim from verified terminal evidence without running learning again | Covered by Part 11-19 crash-window integration test |
| A claim is completed but terminal evidence cannot be restored | The request fails closed rather than re-running learning | Covered by Part 11-20 acceptance test |

## Operational requirements and limits

- Configure `SQLiteEvidenceStore` and `SQLiteReplayClaimStore` with the **same resolved database file**. Kernel initialization rejects mismatched files.
- SQLite coordination is intended for a single host and a local filesystem that correctly supports SQLite locking and WAL semantics. Do not assume an arbitrary network share provides equivalent guarantees.
- Set `timeout_seconds` to a bounded value consistent with the service's latency budget. Handle `sqlite3.OperationalError` as a storage availability failure; retry only through a bounded, observable policy and preserve idempotency keys.
- For live backups, use SQLite's online backup API or a documented quiesced backup procedure that accounts for WAL state. Do not copy only the main database file while writers are active and assume it is a complete snapshot.
- Monitor database free space, write-lock failures, WAL growth/checkpoint behavior, restore-test results, and stale claims. Define retention and backup/restore objectives before production deployment.
- Evidence persistence plus a replay claim does not provide a distributed transaction with arbitrary external effects. Effects that may be repeated after a crash must be idempotent, deduplicated by the downstream service, or included in a shared transactional protocol.
- This audit verifies failure behavior for the covered paths. It is not a substitute for deployment-specific crash testing, restore drills, load tests, or a multi-host datastore design review.
