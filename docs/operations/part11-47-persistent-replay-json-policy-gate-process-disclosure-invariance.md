# Part 11-47 窶・Persistent Replay JSON Policy-Gate Process Disclosure Invariance

## Purpose

Part 11-46 verifies disclosure invariance inside the CLI entry function. This part extends that guarantee across the actual Python module process boundary, including the case where pending reconciliation and expired-claim policy gates fail together.

## Changes

The process contract test creates a synthetic expired claim with canonical terminal evidence and runs `python -m infrastructure.security.persistent_replay_ops check --json` twice with both policy gates enabled: once with default redaction and once with `--include-pending-cycle-ids`.

- Both processes return exit code `2`, preserving pending-reconciliation gate precedence when both gates fail.
- Both JSON reports contain the same gate outcomes and counts; every field apart from the opt-in `pending_reconciliations` detail is identical.
- Standard error is identical and does not disclose the cycle or evidence identifiers.
- Default stdout redacts both identifiers; explicit opt-in stdout includes the expected reconciliation detail.

## Compatibility and safety

This part adds a process-level test and documentation only. It does not change production code, the published JSON Schema, gate exit-code precedence, or default identifier redaction. The test database and identifiers are temporary.

## Validation

Run `validate_patch.ps1`, then the full pytest suite and the Deprecation gate before committing.
