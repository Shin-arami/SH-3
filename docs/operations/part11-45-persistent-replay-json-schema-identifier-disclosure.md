# Part 11-45 窶・Persistent Replay JSON Schema Identifier Disclosure

## Purpose

Part 11-44 verifies that the actual CLI process redacts pending cycle/evidence identifiers by default and includes them only when `--include-pending-cycle-ids` is explicitly supplied. This part connects those two runtime output variants to the published JSON Schema v1 contract.

## Changes

The contract test creates a valid pending terminal-evidence reconciliation and invokes `check --json` both without and with `--include-pending-cycle-ids`.

- The default report contains the pending reconciliation count but omits `pending_reconciliations` and does not emit the cycle/evidence identifiers.
- The explicit opt-in report contains one detail record with the documented fields and identifiers.
- Both reports must remain one-line JSON objects and satisfy the published v1 schema.

## Compatibility and safety

This change adds tests and documentation only. It does not change the CLI implementation, schema, identifier redaction defaults, or exit-code behavior. The fixture identifiers are synthetic and live only in the temporary test database.

## Validation

Run the focused schema and identifier-disclosure process tests, Ruff, and Mypy using the provided validation script. Before committing, run the full pytest suite and Deprecation gate.
