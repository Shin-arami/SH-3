# Part 11-31 — Persistent Replay Pending Evidence Reconciliation

## Purpose

The replay coordinator writes terminal closed-loop evidence and marks the replay claim completed in separate transactions. A process interruption between those writes leaves valid terminal evidence beside a claim that is still `claimed` or has been `released` during failure handling. The next execution can reconcile that state, but the read-only readiness report previously did not surface it.

## Changes

`DatabaseReadinessReport` now includes `pending_evidence_reconciliation_count`, and the persistent replay operations CLI prints the count. For any non-completed claim, the readiness check looks for the canonical evidence identifier derived from the claim's `cycle_id`. When such a record exists, the same kind/source, cycle identity, canonical identifier, and result/subject identity checks used for completed claims are applied before it is counted.

The check remains read-only. A valid pending record is informational and does not make readiness fail by itself: it may indicate a live finalization window or a prior interruption that the replay coordinator can reconcile. The CLI prints a warning so operators can distinguish this state from a database with no pending evidence links. An invalid canonical candidate fails closed.

## Tests

The added tests cover pending evidence beside a still-claimed record, pending evidence beside a released claim, rejection of an invalid terminal-evidence candidate, and CLI reporting of the pending count and warning. They also verify that readiness inspection does not mutate the claim or evidence records.

## Operator guidance

Do not manually edit the claim state or delete evidence to clear this warning. Allow a live owner to finish, or restart through the normal persistent runtime so the coordinator can restore the terminal report and reconcile the claim. Inspect backups and logs first if reconciliation itself fails. This counter is a snapshot, not proof that an owner is or is not currently running.
