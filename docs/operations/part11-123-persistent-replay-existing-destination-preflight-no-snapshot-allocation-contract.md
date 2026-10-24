# Part 11-123 — Existing-Destination Preflight Prevents Snapshot Allocation

## Contract

If the destination already exists when backup or restore begins, the operation must reject it during destination preflight. It must not allocate a temporary snapshot, attempt hard-link publication, overwrite the existing target, or create new matching `.partial` artifacts.

This complements the publication-race contracts: those inject a competing publisher after temporary snapshot creation. This part covers the earlier fail-closed path where the destination is occupied before allocation begins.

## Assertions

- Both backup and restore raise `FileExistsError` with the explicit no-overwrite diagnostic.
- `tempfile.mkstemp` and `os.link` are never called.
- The source/backup input and pre-existing destination remain byte-for-byte unchanged.
- Evidence counts on both databases remain unchanged.
- No new destination-matching `.partial` artifact appears.

## Scope

Test and operations document only. Production code, CLI behavior, and the published persistent-replay JSON Schema are unchanged.

## Validation

Run `validate_patch.ps1` from the SH-3 repository root with `SH3_PYTHON` pointing to Python 3.12 or newer. The validator runs the focused contract test, related snapshot/publication/cleanup/recovery tests, Ruff, Mypy, JSON Schema parsing, the full pytest suite, the deprecation-warning gate, whitespace checks, and `git diff --check`.
