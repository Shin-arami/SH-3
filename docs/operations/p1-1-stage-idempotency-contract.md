# P1-1 — Persistent Stage Idempotency Contract

## Status and scope

This document defines the Stage-level idempotency identity and the SQLite
execution ledger introduced by P1-1.

P1-1 adds the infrastructure contract and persistence adapter only. It does
not yet connect the adapter to `CognitiveLearningBoundary` or execute stages
through it. That integration is P1-2.

## 1. Stable Stage Idempotency Key

A logical Stage is identified by:

- `cycle_id`
- parent replay `cycle_fingerprint`
- `stage_name`
- `input_fingerprint`
- contract version (`1`)

The `input_fingerprint` is SHA-256 over canonical JSON for the Stage input.
The Stage idempotency key is SHA-256 over the canonical identity tuple.

The key deliberately excludes:

- replay-claim generation
- replay-claim owner token
- wall-clock timestamps
- retry attempt count

Therefore, takeover by a newer generation preserves the same key when the
logical Stage and its input are unchanged. A changed input or Stage name
produces a different key.

Only fingerprints are persisted; raw Stage inputs are not stored in the
execution ledger.

## 2. Persistent state machine

`sh3_replay_stage_executions` stores one row per Stage idempotency key.

| State | Meaning |
|---|---|
| `claimed` | A current parent-claim owner has started the Stage |
| `completed` | A canonical JSON result and its SHA-256 digest are durable |

The transition is:

`absent -> claimed -> completed`

A second begin by the same generation and owner is rejected as busy.
A completed Stage returns its stored result and is not claimed again.
An unfinished Stage may be taken over only after the parent replay claim
has moved to a newer generation.

Stage completion validates the parent claim's fingerprint, state, generation,
owner token, and lease deadline in the same SQLite write transaction that
commits the Stage result.

A stale generation cannot complete a Stage after takeover.

## 3. Result persistence and integrity

Stage results are JSON mappings serialized with the repository's canonical
JSON rules. The ledger stores:

- canonical `result_json`
- SHA-256 `result_integrity`
- final Stage state and generation
- attempt count and update timestamp

Reads verify canonical serialization and the result digest. Invalid or
tampered results fail closed with `PersistentEvidenceIntegrityError`.
The operational `check` command validates the Stage table when it exists.

The Stage table is optional for older databases during this infrastructure
phase. Databases without it continue to pass the existing readiness check.
Once created, the table and its rows are validated.

## 4. Fencing and recovery semantics

The Stage ledger is fenced by the parent Replay Claim. It does not create an
independent lease or owner token. Parent heartbeat renewal therefore remains
the authority for liveness.

A completed Stage result can be reused by a later generation, provided the
stable identity matches. An unfinished Stage can be reclaimed by a later
generation with the same idempotency key and an incremented attempt count.

## 5. Exactly-once limitation

The ledger does not make an arbitrary external side effect exactly-once.

A process can perform an external action and crash before committing the
Stage result. After takeover, the Stage ledger cannot infer whether that
external action happened.

To prevent duplicate external effects, the Stage executor or downstream
backend must accept and enforce the stable Stage idempotency key, or the
effect and Stage completion must share a transaction. If neither condition
holds, the effect remains potentially at-least-once across the crash window.

P1-2 must pass the stable key to the Learning Stage backend and explicitly
declare whether the backend enforces it. Unsupported backends must not be
described as exactly-once.

## 6. Deployment boundary

The adapter uses the same SQLite database as `sh3_replay_claims` and is
intended for the repository's documented single-host/local-filesystem SQLite
deployment. It does not establish multi-host coordination on arbitrary
network filesystems.
