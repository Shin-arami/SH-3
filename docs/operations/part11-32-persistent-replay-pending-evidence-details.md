# Part 11-32 — Persistent Replay Pending Evidence Details

## Purpose

Part 11-31 added an aggregate count of canonical terminal evidence found next to a claim that is not yet completed. Counts are useful for alerting but are insufficient for an operator to distinguish a live finalization window from an expired lease or a released claim.

## Changes

`DatabaseReadinessReport` now provides an immutable, deterministically ordered `pending_evidence_reconciliations` tuple. Each record contains only the fields needed for triage:

- `cycle_id` and canonical terminal `evidence_id`;
- claim state, generation, and attempt count;
- lease expiry time and whether the claim lease is expired, when the claim is still in `claimed` state.

Released claims report no lease timestamp and an unknown lease-expiry flag because they do not have an active lease. Owner tokens, fingerprints, and evidence payloads are not included in the detail record.

The CLI continues to print aggregate counts by default. To print cycle-specific details explicitly, operators can run `check --database <path> --include-pending-cycle-ids`. Cycle IDs may contain application result identifiers, so this option should be used only in an appropriately protected terminal or log context.

## Safety boundary

This is still a read-only snapshot. It does not change claims, complete reconciliation, delete evidence, or determine by itself whether an owner process is alive. An unexpired claim with evidence can represent an active finalization window; an expired or released claim needs investigation and normal coordinator reconciliation rather than manual SQL edits.

## Tests

Tests cover the report fields for active, expired, and released claims; agreement between count and detail tuple; default CLI redaction of cycle IDs; and explicit detail output without exposing owner tokens or fingerprints.
