# Part 11-50 - Persistent Replay JSON Argument-Validation Error Disclosure Invariance

## Purpose

Part 11-49 verifies that the identifier-disclosure option does not alter a readiness-error report. This part covers semantically invalid timeout values that pass argparse conversion but are rejected by runtime validation.

## Changes

A process-level contract test invokes `check --json` with timeout values `0`, `nan`, and `inf`, both with default identifier redaction and with `--include-pending-cycle-ids`.

- Each invalid timeout returns exit code `1` and the `invalid_argument` / `ValueError` JSON error envelope.
- Both option variants produce byte-for-byte identical standard output and standard error.
- The private database path is absent from both streams.
- The disclosure option cannot convert an invalid-argument failure into a normal readiness report.

## Compatibility and safety

This change adds a process-level test and documentation only. Production code and the published JSON Schema are unchanged. All paths are temporary and the invalid timeout is rejected before the database is opened.

## Validation

Run `validate_patch.ps1`, then the full pytest suite, the Deprecation gate, and `git diff --check` before committing.
