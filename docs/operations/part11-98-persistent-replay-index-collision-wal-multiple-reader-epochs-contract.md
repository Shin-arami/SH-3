# Part 11-98 — WAL Multiple Reader Epochs and Checkpoint Release Contract

## Purpose

Verify that independent WAL readers pinned to different committed epochs each retain a consistent view and that a `TRUNCATE` checkpoint does not complete while either reader remains active. Releasing only the oldest reader must not let the checkpoint pass the intermediate reader's snapshot. Once both readers finish, the checkpoint must complete and newly opened readers must see both committed epochs.

## Contract

- Exercise both backup-destination and restore-destination flows.
- Hold an initial reader on the base epoch, commit the first write epoch and its probe index, then hold a second reader on that intermediate epoch.
- Commit a second write epoch while both readers remain active. In each write epoch, retry the canonical required-index creation three times inside SAVEPOINTs; each collision must be stable, rolled back locally, and must not disturb the canonical `(state, lease_expires_at)` index.
- Two TRUNCATE checkpoint attempts with both readers active must remain busy and return stable checkpoint counters.
- After the older reader exits, two further checkpoint attempts must remain busy because the intermediate reader is still pinned to epoch one.
- After the second reader exits, TRUNCATE must return `(0, 0, 0)`. The current database must contain both committed user-version markers and both probe indexes, while each historical reader saw only its own snapshot.
- The Readiness Check must emit identical success JSON reports across two runs. Source files, backup files where applicable, and synthetic `.partial` / WAL / SHM / journal residue must remain unchanged.

## Scope

This contract adds a test and this operations document only. Production code, CLI behavior, and the published JSON Schema are unchanged.
