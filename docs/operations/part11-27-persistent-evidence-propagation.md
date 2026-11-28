# Part 11-27 — Persistent Evidence Propagation Audit

## Purpose

Ensure the persistent EvidenceStore supplied to `SH3Kernel` is shared by the typed cognition observability layer and its default `RuntimeExecutionEngine`, in addition to the optimizer and closed-loop evidence boundaries already wired by the persistent kernel factory.

## Changes

- If `SH3Kernel` receives an explicit `evidence_store`, it passes the same store to `CognitionCore` observability and to the default runtime execution engine.
- Kernels constructed without an explicit evidence store keep the existing legacy construction path.
- Updating the kernel's event publisher also updates the configured runtime execution engine publisher.
- The runtime engine's publisher getter/setter validates publisher types and protects configuration writes with its lock.

## Evidence IDs

For a successful typed cognitive execution, the shared database should include evidence records for at least:

- `cognition.result:<result_id>` — typed terminal cognitive result.
- `cognition.execution:<execution_id>` — cognition-stage execution evidence.
- `runtime.execution:<execution_id>` — runtime execution and cleanup evidence.
- `learning.closed_loop` / related terminal closed-loop evidence — the learning, recovery, feedback, and terminal report boundary.

Exact total evidence count may increase as additional stages are added. Acceptance should therefore verify stable record identities and integrity, not depend only on a hard-coded total count.

## Validation

The new acceptance tests use disposable SQLite databases. They assert that cognition observability, runtime execution observability, and closed-loop processing use the same `SQLiteEvidenceStore`; that the three distinct cognition/runtime evidence IDs are present and verifiable; and that the replay claim is completed without expired leases. A separate test ensures publisher replacement propagates to the runtime execution engine.

`SH3Kernel()` without an explicit `evidence_store` must preserve the existing construction path. This patch does not configure a live database or choose an environment-specific path. Production database provisioning and backup/restore remain separate operator-controlled steps.

## Operational limitations

- This audit verifies store wiring and evidence persistence, not business correctness of the payloads.
- A durable evidence record does not make arbitrary external side effects exactly-once. Application operations still require downstream idempotency or transactional guarantees.
- SQLite remains a single-host persistence choice; use a transactional server database adapter for multi-host coordination.
