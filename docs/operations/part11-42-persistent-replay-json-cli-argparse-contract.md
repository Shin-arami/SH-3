# Part 11-42 — Persistent Replay JSON CLI Argument-Parsing Contract

## Purpose

Parts 11-35 through 11-41 define JSON reports for successfully parsed commands and operational failures that happen while a command is running. CLI argument errors occur earlier, inside `argparse`, and must not be mistaken for either a successful report or an operational error envelope.

## Contract

For `check`, `backup`, and `restore`, invocation errors rejected by `argparse` retain the standard CLI behavior:

- The process returns exit code `2`.
- Usage and argument diagnostics are written to stderr.
- Stdout remains empty, even when `--json` is present in the arguments.
- No partial JSON object or Python traceback is emitted.

This differs from an operational error after argument parsing, which uses the JSON error envelope and exit code `1` when JSON output was requested. Policy-gate failures remain exit code `2` or `3` after a readiness check has completed; their JSON report is still emitted. Automation should use command context and stdout/process exit code to distinguish these cases.

## Tests

Subprocess tests cover missing required arguments and invalid numeric timeout values across all three subcommands. The tests use the active Python interpreter, invoke the module without a shell, and do not need a database to exist because parsing rejects the invocation before execution begins.

## Scope and safety

This part adds tests and documentation only. It does not alter the argument parser, JSON Schema v1, exit codes, storage, or backup behavior.
