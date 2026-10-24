# Part 11-81 — Duplicate Index Name Collision Contract

This patch adds a contract test and operations documentation only. Production code, CLI behavior, JSON report fields, and the published JSON Schema are unchanged.

## Scope

SQLite does not permit two indexes with the same schema-level name to coexist. This contract exercises a failed attempt to create a second `sh3_replay_claims_state_idx` using the reversed key order while the canonical index already exists.

The test covers both backup destinations and restore destinations and verifies:

- The conflicting `CREATE INDEX` statement is rejected by SQLite with an `already exists` error.
- The canonical index definition and destination bytes remain unchanged after the rejected repair attempt.
- The protected source/backup files and residual `.partial` / SQLite sidecar artifacts remain unchanged.
- Two consecutive `check --json` calls still return the same successful readiness report, with no stderr diagnostics.

## Operational contract

An operator must not attempt to create a same-name replacement index before dropping the existing index. SQLite rejects that collision without replacing the existing definition. The readiness checker remains diagnostic; it does not repair or rewrite the schema.

If an index genuinely needs correction, perform a deliberate, controlled repair procedure and verify the resulting canonical definition before resuming operations.

## Change boundaries

Only this test and this documentation are added. Production code, CLI behavior, JSON report fields, and the published JSON Schema are unchanged.

## Validation

Run `validate_patch.ps1` from the repository root with Python 3.12+ configured through `SH3_PYTHON`. The script runs the new contract, related index/recovery/JSON CLI regression tests, Ruff, Mypy, JSON Schema syntax validation, the complete pytest suite, the deprecation-warning gate, whitespace validation, and `git diff --check`.
