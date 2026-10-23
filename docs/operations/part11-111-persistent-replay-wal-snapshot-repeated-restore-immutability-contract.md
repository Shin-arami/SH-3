# Part 11-111 — WAL Snapshot Repeated Restore Immutability Contract

## Purpose

Verify that one published SQLite snapshot remains an immutable recovery point when it is restored repeatedly into independent working databases, each working copy is mutated under WAL mode, and multiple checkpoint modes are executed. A later restore from the same snapshot must reproduce the original logical baseline, never the state of a previously mutated restore destination.

## Contract

- Exercise snapshots sourced both directly from the operational database and from a restored copy.
- Preserve the canonical `sh3_replay_claims_state_idx` definition (`sh3_replay_claims(state, lease_expires_at)`, non-unique, non-partial).
- Exercise repeated index-name collisions inside savepoints and ensure only the attempted inner operation is rolled back.
- Mutate and checkpoint independent restore destinations in different checkpoint orders.
- Restore the immutable snapshot again after other working copies have been mutated; verify its original `user_version`, row counts, and index set.
- Preserve source/snapshot bytes and synthetic `.partial`/SQLite sidecar residue artifacts.
- Verify repeated CLI `check --json` output is stable, exits successfully, and emits no stderr.

## Validation

Run `validate_patch.ps1` from the repository root with the Python 3.12+ interpreter selected via `SH3_PYTHON`. The script runs this contract, related WAL/recovery/JSON regressions, Ruff, Mypy, the published schema syntax check, the full pytest suite, the deprecation-warning gate, whitespace checks, and `git diff --check`.

This part adds only a contract test and this operations document. It intentionally does not change production behavior, CLI contracts, or the published JSON Schema.
