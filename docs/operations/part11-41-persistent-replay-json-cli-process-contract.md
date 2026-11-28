# Part 11-41 — Persistent Replay JSON CLI Process Contract

## Purpose

Parts 11-35 through 11-40 define JSON success/error envelopes and policy-gate exit-code invariants. Unit tests invoking `main(argv)` do not prove that the module entry point preserves those contracts across the operating-system process boundary.

## Changes

Add subprocess regression tests that invoke `python -m infrastructure.security.persistent_replay_ops` with the active interpreter. The tests cover:

- JSON success output from `check`, `backup`, and `restore`, including exactly one JSON object on stdout and no diagnostic output on stderr;
- a missing-database failure with process exit code `1`, path-free JSON, and detailed diagnostics restricted to stderr;
- an expired-claim gate failure with process exit code `3` and matching `policy_gates` / `exit_code` fields;
- both policy gates failing in the same process, verifying that pending-reconciliation retains exit-code precedence `2`, both failures are reported on stderr, and cycle/evidence identifiers remain redacted.

The tests invoke subprocesses without a shell and use temporary SQLite databases. They do not mutate repository state or require external services.

## Compatibility and safety

This part adds tests and documentation only. Production CLI code, the published JSON Schema, default output, exit-code values, and storage behavior remain unchanged. Operators and automation must continue to inspect the actual process exit code, not only the JSON payload.

## Validation

Run the focused test file with Python 3.12, then Ruff and Mypy as provided by the patch validation script. Before committing, run the full pytest suite and the Deprecation gate.
