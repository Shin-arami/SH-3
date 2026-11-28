# Part 11-40 — Persistent Replay JSON Policy-Gate Runtime Contract

## Purpose

Part 11-39 tightened JSON Schema v1 so successful reports cannot contain contradictory policy-gate results and exit codes. This part verifies that the real `check --json` CLI output satisfies those rules across passing, single-gate failure, and combined-gate failure states.

## Tests

The contract tests invoke the existing CLI `main()` against temporary SQLite databases and validate the emitted JSON report using the published schema contract test validator. They cover:

- Both opt-in gates pass and the process returns `0`.
- Pending evidence is detected while its claim lease is still active; pending reconciliation fails, the expired-claim gate passes, and the process returns `2`.
- An expired claim without terminal evidence causes the expired-claim gate to fail and returns `3`.
- Both gates fail when an expired claim has canonical terminal evidence; both failures are reported while exit code `2` retains precedence.

The tests assert the JSON `exit_code` field equals the actual return code and that each report validates against the published version-1 schema. Gate diagnostics remain on stderr; stdout remains one JSON document.

## Safety and compatibility

No production Python behavior or schema fields change in this part. It adds runtime conformance coverage only. Database fixtures are created under pytest's temporary directory, and all readiness checks remain read-only.
