# Part 11-78 — Persistent Replay Extra Index Key Column Contract

## Purpose

The required `sh3_replay_claims_state_idx` index must contain exactly the canonical key columns, in order: `state`, then `lease_expires_at`. This contract verifies that an index which preserves the correct owner and required key prefix, but adds an extra ordinary table column, is still rejected by readiness checks.

## Scope

The test covers both backup destinations and restore destinations. For each scenario it replaces the required index with a non-unique, non-partial index on `(state, lease_expires_at, <another actual claim-table column>)` and verifies:

- Three consecutive `check --json` calls report the same readiness failure and diagnostic.
- The readiness check does not auto-repair the index or mutate the destination database, protected sources, or residual `.partial`/SQLite sidecar artifacts.
- Explicitly recreating the canonical two-column index restores a passing readiness check, and two repeated success reports are stable.
- Error output does not disclose absolute paths.

The extra ordinary column is selected from `PRAGMA table_info(sh3_replay_claims)` at runtime, excluding the two required columns. The test therefore does not hard-code a claim-table column name beyond the established schema contract.

## Operational contract

A failed readiness check diagnoses an invalid index definition; it must not silently normalize it. Repair is an explicit operator action. Repeated checks of an unchanged invalid state must remain deterministic and must preserve unrelated source and residual artifacts.

## Change boundaries

This part adds a test and this documentation only. It does not change production code, the CLI, JSON report fields, or the published JSON Schema.

## Validation

Run `validate_patch.ps1` from the repository root using the Python 3.12+ interpreter configured through `SH3_PYTHON`. The script executes the new contract, related index/recovery/JSON CLI regressions, Ruff, Mypy, JSON Schema syntax validation, the full pytest suite, the deprecation-warning gate, whitespace validation, and `git diff --check`.
