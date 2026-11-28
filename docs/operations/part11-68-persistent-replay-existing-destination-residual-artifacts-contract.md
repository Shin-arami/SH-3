# Part 11-68 - Persistent Replay Existing Destination and Residual Artifact Contract

## Purpose

Part 11-67 verifies that a retry after an ambiguous post-publication cleanup failure does not replace an already-published destination. This part isolates the refusal path when the destination already exists and the destination's temporary snapshot family also contains stale `.partial`, `.partial-wal`, `.partial-shm`, and `.partial-journal` artifacts before the retry starts.

## Contract

A deterministic contract test runs both `backup` and `restore` and asserts that:

- an existing destination is rejected using the established sanitized JSON report and nonzero exit code;
- the error diagnostic identifies the refusal but redacts absolute source and destination paths;
- refusal occurs without overwriting the existing destination or modifying the source;
- all pre-existing artifacts associated with the destination's `.partial` snapshot family remain present with byte-for-byte identical content;
- the exact matching artifact set is unchanged, so the refusal path neither removes stale evidence nor creates new temporary artifacts;
- the existing destination remains checkable and its evidence and replay-claim counts remain stable.

## Compatibility and safety

This is a regression-test and operations-documentation addition only. Production code, CLI arguments, JSON report fields, and the published JSON Schema are unchanged. The test creates its own temporary database and synthetic stale artifacts under pytest's temporary directory; it does not touch persistent user data.

## Operator recovery

When an existing destination and stale `.partial` artifacts coexist, do not assume a failed invocation means publication did not occur. Verify the destination independently, preserve the residual artifacts for diagnosis, and decide on an explicit cleanup or recovery action only after the destination's state is understood. A retry that refuses to overwrite must not silently clean up or rewrite those artifacts.

## Validation

Run `validate_patch.ps1` from the repository root with Python 3.12+. It runs this contract, related Backup/Restore safety contracts, Ruff, Mypy, published JSON Schema syntax validation, the full pytest suite, the deprecation-warning gate, and `git diff --check`.
