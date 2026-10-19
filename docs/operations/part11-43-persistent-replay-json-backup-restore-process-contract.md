# Part 11-43 窶・Persistent Replay JSON Backup/Restore Process Contract

## Purpose

Part 11-37 defined JSON reports for backup and restore, and Part 11-41 verified the primary CLI process boundary. Error envelopes for backup/restore were tested through `main(argv)`, but destination conflicts and missing backup paths also need process-level coverage because automation observes process exit codes, stdout, and stderr separately.

## Changes

Add subprocess tests for three failure cases:

- `backup --json` refuses an existing destination, emits exactly one JSON error envelope to stdout, returns `1`, writes detailed diagnostics to stderr, and leaves the destination bytes unchanged.
- `restore --json` with a missing backup returns `1`, emits the stable `database_not_found` envelope without exposing the path on stdout, writes diagnostics to stderr, and does not create the destination.
- `restore --json` refuses an existing destination, emits the stable `destination_exists` envelope, and leaves the destination bytes unchanged.

The tests invoke `python -m infrastructure.security.persistent_replay_ops` using the active interpreter, without a shell, and use temporary SQLite files.

## Compatibility and safety

This part adds tests and documentation only. Production code, JSON Schema v1, operation behavior, and exit-code definitions are unchanged. The no-overwrite guarantee remains covered at the actual subprocess boundary. Error responses continue to separate path-bearing diagnostic text on stderr from path-free JSON on stdout.

## Validation

Run the new test file along with the existing backup/restore unit and process-contract tests. Run Ruff, source Mypy, and both the complete pytest suite and Deprecation gate before committing.