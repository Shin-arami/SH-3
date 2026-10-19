# Part 11-52 - Persistent Replay Backup/Restore Timeout Error Process Contract

## Purpose

Part 11-50 covers semantically invalid timeout values for the `check` operation. This part verifies the same validation boundary across the shared backup/restore snapshot path, including the action-specific JSON error envelope and the guarantee that invalid input causes no filesystem side effects.

## Changes

A process-level test runs `backup` and `restore` with timeout values `0`, `nan`, and `inf`.

- Every invocation exits with code `1` and emits exactly one JSON error object.
- The error envelope identifies the correct action and reports `invalid_argument` / `ValueError`.
- Standard error contains the stable timeout diagnostic and does not contain the source or destination paths.
- The source and destination paths remain absent because timeout validation happens before database access or destination creation.

## Compatibility and safety

This change adds six process-level cases and documentation only. It does not modify production code or the published JSON Schema. All paths are private temporary paths; invalid timeout values are rejected before filesystem operations.

## Validation

Run `validate_patch.ps1`, then the full pytest suite, the Deprecation gate, and `git diff --check` before committing.
