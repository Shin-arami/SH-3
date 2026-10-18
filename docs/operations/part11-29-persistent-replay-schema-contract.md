# Part 11-29 — Persistent Replay SQLite Schema Contract

## Purpose

The persistent replay readiness check previously verified that expected column names existed, but did not confirm that the tables preserved the key and nullability guarantees used by the SQLite adapters. A table with the right column names but no canonical primary key could therefore pass the schema gate even though the storage contract had changed.

## Changes

`check_database()` remains read-only and now validates these schema invariants before reading evidence or claims:

- `sh3_evidence_records` uses `evidence_id` as its sole primary key.
- Every evidence table column required by the adapter is declared `NOT NULL`.
- `sh3_replay_claims` uses `cycle_id` as its sole primary key.
- Claim identity, fingerprint, state, generation, attempts, and update timestamp columns are declared `NOT NULL`; ownership, lease, and evidence-link columns retain their intended nullable semantics.

A schema mismatch raises `PersistentReplayReadinessError`. The check does not migrate, repair, rewrite, or delete data. Operators should preserve the database and inspect the schema or restore a separately verified backup before retrying runtime startup.

## Tests

The new tests verify rejection of a missing evidence primary key, a missing claim primary key, a nullable required evidence column, a nullable required claim column, and acceptance of the schema created by the SH-3 SQLite store adapters.

## Scope boundary

This is a structural readiness gate, not a schema migration system and not proof of atomicity for external side effects. It intentionally does not create a production database or change runtime provisioning behavior.
