# P3-2G G-B — Persisted Action Compatibility Contract

## Purpose

Persistent optimizer replay must not reuse an Action or Rollback result under a different implementation contract. Function source-code hashing is deliberately not used: source text, bytecode, file paths, and build artifacts are not stable semantic compatibility identifiers.

## Required metadata for durable Actions

Every `OptimizationAction` used with the persistent replay operation store must declare all three non-empty string fields:

- `contract_id`: stable semantic identity of the Action contract; keep it stable while the meaning of the contract remains the same.
- `implementation_version`: increment when the Action implementation, accepted semantic input, side-effect behavior, or result meaning changes incompatibly.
- `rollback_version`: increment when compensation behavior or rollback semantics change incompatibly.

`replay_policy` is also part of the persisted plan contract. The three metadata fields may all be omitted for non-durable/in-memory optimizer use. Supplying only some of them is invalid. The built-in Actions declare explicit version `1` values. Custom durable Actions must declare their own contract metadata.

Version numbers are developer-managed compatibility assertions. A code change that affects replay semantics must be accompanied by an appropriate version increment and a regression test.

## Persisted plan format

Action Plan version 2 stores the ordered list of Action descriptors:

- Action name
- Contract identifier
- Implementation version
- Rollback version
- Replay policy

On retry, the current registered descriptors must exactly match the immutable persisted plan before any Action is executed or any completed Action result is reused. A mismatch fails closed.

The durable operation input fingerprint also includes the Action descriptor. This protects the direct single-Action execution path, which does not create an ordered Action Plan. Rollback operation fingerprints include the same descriptor so a changed compensation contract cannot reuse an earlier Rollback outcome.

## Legacy version-1 records

Version-1 plans contain Action names only and therefore cannot prove which Action or Rollback implementation produced an earlier result. They are not silently upgraded or automatically assigned the current code's versions. The new readiness validator rejects version-1 plans, and execution rejects them rather than assuming compatibility.

Before deploying this change against a database containing version-1 plans, take a verified backup and reconcile every affected cycle using the previously deployed code. Do not delete or rewrite historical plan/operation rows to bypass the compatibility check. A separate, reviewed migration is required if those records must remain replayable under the new contract format.

## Verification

The G-B tests cover:

- Stable same-contract replay after Runtime restart.
- Same Action name with a changed implementation version.
- Same Action name with a changed Rollback version.
- Direct durable single-Action execution with a changed compatibility version.
- Rejection of legacy name-only version-1 plans.
