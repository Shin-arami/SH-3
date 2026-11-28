# Part 11-80 — Reversed Index Key Order Contract

This patch adds a contract test and operations documentation only. Production code, CLI behavior, JSON report fields, and the published JSON Schema are unchanged.

## Scope

The required `sh3_replay_claims_state_idx` index must use the ordered key columns `(state, lease_expires_at)`. This contract keeps the expected owner, index name, non-unique property, non-partial property, and the same two columns, but reverses their key order to `(lease_expires_at, state)`.

The test covers both backup destinations and restore destinations and verifies:

- Three consecutive `check --json` calls report the same readiness failure and diagnostic while the required key order is reversed.
- The checker does not repair or rewrite the index and does not mutate the destination, protected sources, or residual `.partial` / SQLite sidecar artifacts.
- An explicit operator repair that recreates the index with the canonical `(state, lease_expires_at)` order restores a passing check; two repeated success reports remain stable.
- Failure output does not disclose absolute paths.

## Operational contract

Column membership alone is insufficient: the key order is part of the required index definition. The readiness check is diagnostic and must not automatically repair a noncanonical index. Repair is an explicit operator action.

## Change boundaries

Only this test and this documentation are added. Production code, CLI, JSON report fields, and the published JSON Schema are unchanged.

## Validation

Run `validate_patch.ps1` from the repository root with Python 3.12+ configured through `SH3_PYTHON`. The script runs the new contract, related index/recovery/JSON CLI regression tests, Ruff, Mypy, JSON Schema syntax validation, the complete pytest suite, the deprecation-warning gate, whitespace validation, and `git diff --check`.
