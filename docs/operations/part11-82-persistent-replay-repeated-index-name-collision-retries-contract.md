# Part 11-82 — Repeated Index Name Collision Retry Contract

This patch adds a contract test and operations documentation only. Production code, CLI behavior, JSON report fields, and the published JSON Schema are unchanged.

## Scope

Part 11-81 verified that SQLite rejects one attempt to create a second index with the existing name `sh3_replay_claims_state_idx`. This contract repeats the conflicting DDL three times against each supported destination type: a backup destination and a restore destination.

For every rejected attempt, the test verifies:

- SQLite returns the same `already exists` error.
- The canonical index remains owned by `sh3_replay_claims`, non-unique and non-partial, with key columns `(state, lease_expires_at)`.
- Destination bytes, protected source/backup bytes, and pre-existing `.partial` / SQLite sidecar artifacts remain unchanged.
- A subsequent `check --json` succeeds with empty stderr and the same readiness report as every other attempt.

## Operational contract

Repeated failed repair attempts must remain non-destructive and must not drift the schema or surrounding artifacts. The readiness check is diagnostic and does not replace the existing index. Operators should use a controlled, explicit repair procedure if the index definition actually needs to change.

## Change boundaries

Only this test and this documentation are added. Production code, CLI behavior, JSON report fields, and the published JSON Schema are unchanged.

## Validation

Run `validate_patch.ps1` from the repository root with Python 3.12+ configured through `SH3_PYTHON`. The script runs the new contract, related index/recovery/JSON CLI regression tests, Ruff, Mypy, JSON Schema syntax validation, the complete pytest suite, the deprecation-warning gate, whitespace validation, and `git diff --check`.
