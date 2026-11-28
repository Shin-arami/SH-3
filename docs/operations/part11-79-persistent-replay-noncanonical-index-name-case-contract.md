# Part 11-79 — Persistent Replay Noncanonical Index Name Case Contract

## Purpose

The readiness contract requires the canonical index name `sh3_replay_claims_state_idx` to be stored exactly as specified. SQLite resolves SQL identifiers case-insensitively, but a differently cased name in `sqlite_master` is not the exact canonical catalog name. This contract verifies that the readiness check does not accept that altered catalog state as canonical.

## Scope

The test covers both backup destinations and restore destinations. It replaces the required index with an otherwise identical non-unique, non-partial index named `SH3_REPLAY_CLAIMS_STATE_IDX` and verifies:

- Three consecutive `check --json` calls report the same readiness failure and diagnostic that the required canonical index is missing.
- The readiness check does not auto-rename or recreate the index and does not mutate the destination, protected sources, or residual `.partial`/SQLite sidecar artifacts.
- Explicitly recreating the index under the exact canonical name restores a passing readiness check, and two repeated success reports are stable.
- Error output does not disclose absolute paths.

## Operational contract

The readiness check is diagnostic, not a schema-repair operation. It must reject a catalog state that does not meet the canonical index-name contract and must remain deterministic when the invalid state is unchanged. Repair is an explicit operator action.

## Change boundaries

This part adds a test and this documentation only. It does not change production code, the CLI, JSON report fields, or the published JSON Schema.

## Validation

Run `validate_patch.ps1` from the repository root using the Python 3.12+ interpreter configured through `SH3_PYTHON`. The script executes the new contract, related index/recovery/JSON CLI regressions, Ruff, Mypy, JSON Schema syntax validation, the full pytest suite, the deprecation-warning gate, whitespace validation, and `git diff --check`.
