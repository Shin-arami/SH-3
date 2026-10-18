# Part 11-30 — Persistent Replay State Schema Contract

## Purpose

Part 11-29 verifies the persistent replay tables' required columns, primary keys, and nullability. This part completes two additional structural checks for the replay claim table: the database-level state-domain constraint and the lease/state access-path index.

## New read-only checks

`check_database()` now requires the `sh3_replay_claims.state` column to enforce exactly the adapter-supported values `claimed`, `completed`, and `released`. Checking current rows alone is insufficient: a table without the `CHECK` constraint may contain valid rows at inspection time but permit invalid state values to be written later.

The readiness check also requires `sh3_replay_claims_state_idx` to be a non-unique, non-partial index with ordered columns `(state, lease_expires_at)`, matching the SQLite adapter's claim-state and lease-expiry lookup path.

Both checks inspect SQLite schema metadata only. They do not create indexes, rewrite schema, repair the database, or delete data. Any mismatch fails closed with `PersistentReplayReadinessError`.

## Tests

Tests cover the adapter-created schema, a missing state check, a missing index, a wrong index-column order, and a partial index with otherwise matching columns.

## Scope boundary

This is a read-only readiness check, not a schema migration mechanism. If the check fails, preserve the database and use a separately verified backup or a planned migration after investigating the schema difference.
