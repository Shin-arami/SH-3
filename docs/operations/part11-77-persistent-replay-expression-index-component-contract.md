# Part 11-77 — Persistent Replay Expression Index Component Contract

## Purpose

Verify that readiness checks reject a non-canonical `sh3_replay_claims_state_idx` whose owner and ordinary key columns are correct but which contains an additional expression key component. The required index must consist of exactly `(state, lease_expires_at)`; appending the expression `(1)` is not an equivalent definition.

## Coverage

The contract exercises both backup destinations and restore destinations. It preserves the canonical index name, owner, uniqueness flag, partial-index flag, and first two key columns while appending an expression component. Three consecutive `check --json` calls must return identical readiness-failure JSON and diagnostics. Checks must not normalize the schema, modify protected source/backup/destination bytes, or change `.partial`, `.partial-wal`, `.partial-shm`, and `.partial-journal` residual artifacts.

After explicit operator repair recreates the canonical two-column index, two consecutive checks must pass with stable JSON output and without changing protected database bytes or residual artifacts.

## Operational contract

Matching the expected index name and a prefix of the expected columns is insufficient. The complete ordered key definition must match the required tuple exactly, with no extra expression or column. A readiness check reports an invalid definition but does not repair it or clean residual files; repair remains an explicit operator action.

## Scope

This part adds a contract test and this operations document only. Production code, CLI behavior, JSON report fields, and the published JSON Schema are unchanged.
