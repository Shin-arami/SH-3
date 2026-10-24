# Part 11-83 — Case-Insensitive Index Name Collision Contract

This patch adds a contract test and operations documentation only. Production code, CLI behavior, JSON report fields, and the published JSON Schema are unchanged.

## Scope

Part 11-82 verified that repeated attempts to create a second index with the exact existing name are rejected. This contract exercises SQLite's case-insensitive identifier collision behavior: while the canonical `sh3_replay_claims_state_idx` exists, it attempts to create `SH3_REPLAY_CLAIMS_STATE_IDX` with a deliberately different key order. The alternate spelling must not bypass the existing index-name constraint.

For both a backup destination and a restore destination, the test retries the conflicting DDL three times and verifies that:

- Each attempt raises the same SQLite `already exists` error.
- The stored index name, owner table, uniqueness flag, partial flag, and key order remain canonical.
- Destination and protected source/backup bytes remain unchanged.
- Existing `.partial` and SQLite sidecar artifacts remain byte-for-byte unchanged.
- Every subsequent `check --json` returns the same successful readiness report and writes no stderr output.

## Operational contract

A case-only spelling change does not create a distinct SQLite index identifier. Failed attempts to evade a schema-name collision must have no side effects; the readiness check remains observational and does not attempt repair. Operators should make schema changes only through the established, explicit repair procedure.

## Change boundaries

Only this test and this documentation are added. Production code, CLI behavior, JSON report fields, and the published JSON Schema are unchanged.

## Validation

Run `validate_patch.ps1` from the repository root with Python 3.12+ configured through `SH3_PYTHON`. The script runs the new contract, related index/recovery/JSON CLI regression tests, Ruff, Mypy, JSON Schema syntax validation, the complete pytest suite, the deprecation-warning gate, whitespace validation, and `git diff --check`.
