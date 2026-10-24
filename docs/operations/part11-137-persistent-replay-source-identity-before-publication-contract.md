# Part 11-137 — Source Identity Recheck Before Snapshot Publication

## Purpose

The snapshot workflow checks the source database identity before preflight and around online backup. This contract closes the remaining gap after the temporary snapshot has been verified but before its hard-link publication is attempted.

## Contract

- Backup and restore recheck the source file identity after temporary snapshot verification and immediately before publication.
- If the source identity no longer matches the identity captured at operation start, the operation raises `PersistentReplayReadinessError` with the `before snapshot publication` phase.
- The verified temporary snapshot is not published to the destination; temporary files are cleaned by the existing cleanup path.
- Existing source and backup database artifacts remain unchanged.
- Once the injected identity drift is removed, a retry to the same destination succeeds.

## Scope

This part changes the snapshot implementation and adds contract coverage plus this operations note. The CLI surface and the published persistent replay report JSON Schema are unchanged.

## Validation

Run `validate_patch.ps1` from the repository root with `SH3_PYTHON` set to the supported Python 3.12+ interpreter. The script runs the focused contract, related snapshot/publication/cleanup/recovery tests, Ruff, Mypy, schema parsing, the full pytest suite, the deprecation-warning gate, whitespace checks, and `git diff --check`.
