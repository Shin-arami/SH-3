# Part 11-140 — Read-Only Source Close and Temporary Cleanup Failure Aggregation

## Contract

When the final source-file identity check fails immediately before publication, the original `PersistentReplayReadinessError` remains primary even if cleanup of the temporary snapshot also fails and closing the read-only source connection fails. The two cleanup issues are reported as distinct exception notes; publication is not attempted and existing source/backup artifacts remain unchanged.

## Fault injection

The test marks the source identity as changed after successful temporary snapshot verification, injects a one-shot failure while unlinking the temporary `.partial` file, and uses a SQLite connection factory whose source connection closes and then raises. Both backup and restore scenarios are exercised.

## Recovery

The test checks that the sole temporary residue remains discoverable, explicitly removes it after fault injection is disabled, and retries to the same destination. It then verifies the destination report and that source/backup artifact bytes are unchanged.

## Compatibility

This part adds test coverage and operations documentation only. Production code, CLI output, and the published JSON Schema are unchanged.
