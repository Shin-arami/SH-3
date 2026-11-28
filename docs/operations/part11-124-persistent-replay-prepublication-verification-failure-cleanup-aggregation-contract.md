# Part 11-124 — Pre-publication verification failure with cleanup aggregation

## Contract

When snapshot verification fails after SQLite has produced a temporary snapshot, cleanup still attempts every temporary artifact. If cleanup itself fails for both a WAL sidecar and the temporary `.partial` database, the original verification exception remains the primary exception and records a diagnostic note describing the incomplete cleanup and recovery guidance.

The contract applies to both backup and restore operations. It also requires that publication is not attempted, the destination remains absent, the input database artifacts remain byte-for-byte unchanged, and a retry succeeds after the injected orphan artifacts are removed.

## Scope

- Add contract tests and this operations note only.
- Do not change production code, CLI output, or the published JSON Schema.
- The test injects a post-check verification failure on the temporary snapshot, plus two cleanup failures. The real source preflight and snapshot creation remain in effect.

## Validation

Run `validate_patch.ps1` from the repository root using the Python 3.12+ interpreter selected through `SH3_PYTHON`. The script runs the focused contract, related snapshot/publication/cleanup regressions, Ruff, Mypy, JSON Schema syntax validation, the full pytest suite, the deprecation-warning gate, whitespace validation, and `git diff --check`.
