# Part 11-75 — Persistent Replay Invalid Index Properties Contract

## Purpose

Verify that readiness checks reject an incomplete repair when the required replay-claim index exists with the expected key columns but has invalid index properties. The canonical `sh3_replay_claims_state_idx` must be a non-unique, non-partial index over `(state, lease_expires_at)`.

## Coverage

The contract exercises both backup destinations and restore destinations. For each path, it separately models:

- a `UNIQUE` index over the expected columns;
- a partial index over the expected columns.

For every invalid definition, three consecutive `check --json` executions must return the same readiness-failure JSON and the same sanitized diagnostic. The readiness operation must not auto-repair the index, write to the destination database, modify the source/backup databases, or change the contents or presence of `.partial`, `.partial-wal`, `.partial-shm`, and `.partial-journal` residual artifacts.

After an explicit test/operator repair recreates the canonical non-unique, non-partial index, repeated checks must pass with stable JSON output and without changing protected bytes or residual artifacts.

## Operational contract

A required index name and matching key-column order do not establish schema readiness by themselves. Index uniqueness and partial-index semantics are part of the contract. A failed readiness check remains observational: it reports the invalid state rather than repairing the database automatically. Repair is an explicit operator action followed by a fresh readiness check.

## Scope

This part adds a contract test and this operations document only. Production code, CLI behavior, JSON report fields, and the published JSON Schema are unchanged.
