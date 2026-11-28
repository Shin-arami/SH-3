# Part 11-38 — Persistent Replay JSON Schema Contract

## Purpose

Parts 11-35 through 11-37 made the `check`, `backup`, and `restore` commands machine-readable. This part publishes a versioned JSON Schema so external automation can validate successful reports and error envelopes without depending on SH-3 internals.

## Contract

The schema is `docs/operations/schemas/persistent-replay-report-v1.schema.json`, using JSON Schema Draft 2020-12. It describes two mutually exclusive envelopes:

- Success: `integrity_status` is `pass`; required summary fields and counts are typed; actions are `check`, `backup`, or `restore`; normal and policy-gate exit codes are `0`, `2`, or `3`.
- Error: `integrity_status` is `error`; `error.code` uses the stable operation-error categories; `exit_code` is `1`; policy-gate results are empty because inspection did not complete.

The optional `pending_reconciliations` array is only emitted when `--include-pending-cycle-ids` is explicitly selected. The schema does not require those identifiers to be emitted.

## Compatibility policy

The `schema_version` remains `1` for this contract. Changes to required fields, field meaning, data types, allowed enum values, or the success/error envelope boundary require an intentional schema compatibility decision. The schema disallows undocumented properties to make output drift visible during validation.

The project has no runtime dependency on a JSON Schema library. The focused tests validate representative success and error output for all three commands against the published schema using a small test-only validator for the schema features this document uses. Consumers may use any conforming Draft 2020-12 validator.

## Safety boundary

This part adds a contract document and tests only. It does not change CLI behavior, exit codes, storage operations, or sensitive identifier redaction. Success reports intentionally retain the database destination path, as documented in Part 11-37; error envelopes continue to omit paths and exception messages from JSON stdout.
