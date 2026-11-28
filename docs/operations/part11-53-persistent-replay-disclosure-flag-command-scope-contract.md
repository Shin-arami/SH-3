# Part 11-53 - Persistent Replay Disclosure Flag Command-Scope Contract

## Purpose

Part 11-51 verifies that `--include-pending-cycle-ids` does not change `check` command parse failures. This part fixes the complementary command-scope boundary: the disclosure option is specific to `check` and must be rejected by `backup` and `restore`.

## Changes

The process-level contract test invokes both `backup` and `restore` with valid required positional options, `--json`, and the check-only `--include-pending-cycle-ids` flag.

- Both commands reject the unsupported option with argparse exit code `2`.
- Standard output remains empty, so no operation JSON envelope is emitted.
- Standard error identifies the correct command and the unrecognized option, without a traceback or supplied filesystem paths.
- Neither source/backup input nor destination files are created by argument parsing.

## Compatibility and safety

This is a test and documentation change only. It does not alter the CLI parser, production code, error envelope, or published JSON Schema. All paths are private paths under pytest's temporary directory.

## Validation

Run `validate_patch.ps1`, then the full pytest suite, the Deprecation gate, and `git diff --check` before committing.
