# Part 11-51 - Persistent Replay JSON CLI Parse-Error Disclosure Invariance

## Purpose

Parts 11-49 and 11-50 cover errors raised after argument parsing, where the CLI can emit a versioned JSON error envelope. This part locks down the separate argparse boundary: parser failures happen before operation handling and must remain usage errors even when identifier disclosure is requested.

## Changes

The process contract test runs two malformed `check` invocations with and without `--include-pending-cycle-ids`: one missing the required database argument, and one with a timeout value that cannot be converted to a float.

- Both variants return argparse exit code `2`.
- Both variants produce empty standard output, rather than an operation JSON envelope.
- Standard error is byte-for-byte identical and contains usage/error text without a traceback.
- The disclosure flag does not change the parser result or reveal the supplied database path.

## Compatibility and safety

This is a test and documentation change only. It does not alter the CLI parser, JSON error envelope, published schema, or runtime implementation.

## Validation

Run `validate_patch.ps1`, then the full pytest suite, the Deprecation gate, and `git diff --check` before committing.
