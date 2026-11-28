# Part 11-112 — WAL Failed Restore Isolation and Retry Contract

## Purpose

Verify that an invalid backup snapshot or an existing destination causes restore to fail without damaging the published snapshot, an existing working copy, or unrelated residual artifacts. A later restore from the valid snapshot must still succeed.

## Contract

- An invalid snapshot missing `sh3_replay_claims_state_idx` is rejected during source preflight.
- A preflight failure does not publish a destination or leave generated `.partial` files behind.
- Restore refuses to overwrite an existing destination and preserves its bytes.
- A failed restore does not mutate the valid source database, published snapshot, protected restored copy, or deliberately seeded residual sidecars.
- After an invalid-source failure, a valid restore to the same path succeeds.
- After a destination-collision failure, a valid restore to a new path succeeds while the existing destination remains unchanged.
- Restored databases retain the expected `user_version`, replay schema, index ownership, ordered columns, and readiness counts.
- Repeated CLI `check --json` observations produce the same report, exit with code 0, emit no standard error, and do not change the restored database bytes.

## Scope

This part adds a contract test and this operations document only. It does not change production code, CLI behavior, or the published JSON Schema.

## Validation

Run `validate_patch.ps1` from the repository root. The gate covers the focused contract, related WAL/snapshot/recovery/JSON regressions, Ruff, Mypy, JSON Schema syntax, full pytest, the deprecation-warning gate, whitespace, and `git diff --check`.
