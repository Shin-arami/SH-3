# Part 11-61 - Persistent Replay Backup/Restore Source Identity Stability Contract

## Purpose

Part 11-60 closes the destructive post-publication rollback race. This part addresses a separate input-side gap: the source is checked by path and then opened again for the online snapshot. If the source pathname is replaced with another valid SQLite database during that interval, the snapshot could otherwise come from a different file than the one validated during preflight.

## Contract

Deterministic tests exercise both `backup` and `restore` while injecting an observable source-identity drift during snapshot creation. The injected identity drift is platform-neutral and does not rename an open SQLite file.

- Capture the resolved source file identity before readiness preflight.
- Recheck the identity after preflight and immediately before snapshot creation.
- Recheck the identity after the online snapshot returns and before snapshot verification/publication.
- If a checkpoint observes a different source identity, fail closed using the existing readiness-error envelope.
- Do not publish the destination or write to the source file; clean the temporary snapshot. The fault-injection test verifies the source bytes remain unchanged and the destination is never published.
- Keep the published CLI arguments and JSON Schema unchanged.

## Scope note

This is a checkpoint-based identity stability guard using the filesystem's device and inode/file-index metadata. It detects a source-path replacement that remains observable at a checkpoint. It is not a claim of protection against a privileged actor deliberately swapping a path away and back between checks; pinning one open SQLite connection through both verification and backup would be a separate, broader refactor.

## Validation

Run `validate_patch.ps1`, inspect the production diff and staged changes, then run `git diff --cached --check` before committing. Validation covers the new race contract, related Backup/Restore regressions, Ruff, Mypy, published JSON Schema syntax, the complete pytest suite, and the deprecation-warning gate.
