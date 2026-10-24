# Part 11-76 — Persistent Replay Misplaced Index Ownership Contract

## Purpose

Verify that readiness checks reject an interrupted repair where the required index name and key-column sequence exist in SQLite, but the index belongs to a different table. The canonical `sh3_replay_claims_state_idx` must belong to `sh3_replay_claims` and index `(state, lease_expires_at)`.

## Coverage

The contract exercises both backup destinations and restore destinations. It relocates the required index definition to a decoy table while leaving its name and key columns unchanged. Three consecutive `check --json` calls must return the same readiness-failure JSON and sanitized diagnostic. The checks must not move or recreate the index, modify source/backup/destination bytes, or change the contents or presence of `.partial`, `.partial-wal`, `.partial-shm`, and `.partial-journal` residual artifacts.

After explicit operator repair drops the misplaced index/table and recreates the canonical index on `sh3_replay_claims`, two consecutive checks must pass with stable JSON output and without changing protected database bytes or residual artifacts.

## Operational contract

An index's name and key columns do not prove that it supports the intended table. Readiness validation must confirm that the required index is attached to the replay-claims table. A failed check reports the invalid state; it never performs schema repair or residual-file cleanup. Repair remains an explicit operator action followed by a fresh readiness check.

## Scope

This part adds a contract test and this operations document only. Production code, CLI behavior, JSON report fields, and the published JSON Schema are unchanged.
