# Part 11-110 — WAL Snapshot Generation Isolation Contract

## Scope

This contract verifies that two published online-backup generations remain immutable and independently restorable while their source proceeds through additional committed write epochs and WAL checkpoints. It covers both direct source writes (`backup-generations`) and writes performed on a restored working copy (`restored-working-copy`).

## Contract

- Generation 1 captures the original committed `user_version`, claim/evidence counts, and canonical `sh3_replay_claims_state_idx` definition.
- The first write epoch creates only its probe index and marker; three attempts to create the required index must fail identically and be rolled back to the savepoint.
- The second published snapshot captures generation 1, including its probe index, before any second-epoch write occurs.
- The second write epoch and an alternate checkpoint-mode sequence must not change either published snapshot.
- Restoring generation 1 must reproduce the original marker and schema, without either probe index. Restoring generation 2 must reproduce the first marker and first probe index, without the second probe index.
- Readiness CLI output must be stable, error-free, and must not mutate published snapshots, protected sources, or residual temporary artifacts.

## Validation

Run `apply_patch.ps1` from the repository root, then run `validate_patch.ps1` with `SH3_PYTHON` pointing at the Python 3.12+ interpreter. The gate includes the focused test, WAL/index/recovery/JSON regressions, Ruff, Mypy, published JSON Schema syntax, the full pytest suite, the deprecation-warning gate, whitespace checks, and `git diff --check`.

No production code, CLI behavior, or published JSON Schema changes are part of this contract.
