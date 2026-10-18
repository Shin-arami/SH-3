# Part 11-28 — Persistent Replay Claim-to-Evidence Link Integrity

## Purpose

A completed replay claim must point to the exact, integrity-verified terminal closed-loop evidence for the same cycle. SQLite integrity and evidence-record hashes alone do not establish this cross-table relationship. The read-only operational check therefore validates completed-claim references after validating evidence records and claim-state invariants.

## New operational checks

For each completed row in `sh3_replay_claims`, `check_database()` now requires:

1. The referenced evidence row exists and passed the existing evidence hash and row-key checks.
2. The record is `kind="learning.closed_loop"` and `source="kernel.learning_feedback_loop"`.
3. The evidence payload's `cycle_id` matches the claim's `cycle_id`.
4. The evidence identifier is the canonical `short_id(cycle_id, prefix="learning-closed-loop:")` used by the restore path.
5. The evidence record's `subject_id` matches its embedded `result_id`.

The check remains read-only. It does not repair, delete, release, or complete replay claims, and it does not rewrite evidence records. Any mismatch fails the readiness check and should block recovery cutover until investigated.

## Acceptance tests

The new tests cover a valid completed link, a missing evidence row, a link to a different cycle, a non-terminal evidence kind/source, a noncanonical evidence identifier, and mismatched result identity. Existing claimed/released rows keep their previous validation behavior; only completed claims require a terminal evidence reference.

## Operational response

If the readiness check reports a broken link, preserve the database and logs, avoid manual SQL updates, and restore to a separate path from a verified backup if recovery is needed. This audit validates the cross-reference that permits replay restoration; it does not prove external side effects were committed atomically with the evidence.
