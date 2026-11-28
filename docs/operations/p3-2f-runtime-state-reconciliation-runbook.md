# P3-2F-D - Runtime State Reconciliation Runbook

## 1. Purpose and scope

This runbook defines the operator response when a durable Optimizer Action or
Rollback result exists but the current Runtime cannot prove that its in-memory
state matches the state represented by that result.

The Operation Ledger is the durable record of callback outcomes. It is not a
snapshot of `ContextManager`, `PolicyEngine`, `MemoryCore`, or arbitrary
Runtime-local objects. A completed ledger row must not be interpreted as proof
that a restarted Runtime has reconstructed the old in-memory mutation.

This runbook describes an operator decision process. It does not introduce an
automatic reconciliation engine or a general-purpose state restoration API.

## 2. Governing invariants

1. Do not rerun a completed Action or Rollback using its existing idempotency
   key.
2. Do not edit, delete, or manually complete a persisted Operation row to make
   a workflow appear healthy.
3. Do not lower or replace the Replay Claim generation, owner token, Action
   identity, input fingerprint, or result integrity value.
4. Do not interpret `state_uncertain=false` as proof of a successful external
   side effect. It only describes the local Action/Rollback result contract.
5. Keep the workflow fail-closed while the authoritative Runtime state cannot
   be established.
6. Any corrective mutation must be an explicitly approved, separately
   identified operation with its own idempotency identity and audit evidence.
   Do not disguise a correction as a retry of the original completed
   Operation.

## 3. Reconciliation decision matrix

| Persisted outcome | Restart interpretation | Automatic behavior | Operator disposition |
|---|---|---|---|
| Completed Action, `success=true`, `changed=false` | The callback explicitly reported no local mutation | Result may be reused under `REQUIRE_LOCAL_STATE` | Verify the Action contract really guarantees no state mutation; no corrective mutation is expected |
| Completed Action, `success=true`, `changed=true` | A mutation occurred in the former Runtime; its state is not restored by the Operation row | Fail closed with `state_uncertain=true`; do not invoke callback again | Compare the current Runtime with an authoritative source or snapshot; restore or correct through a separately approved operation |
| Completed Action, `success=true`, `changed` absent, malformed, or unknown | The mutation status cannot be proven | Fail closed with `state_uncertain=true`; do not invoke callback again | Treat as potentially changed; investigate before resuming |
| Completed Action, `success=false`, `state_uncertain=true` | Callback failed; it may have partially mutated state before raising | Reuse the recorded failure; do not rerun the callback | Inspect actual state and callback-specific evidence; determine whether forward repair or compensation is required |
| Completed Rollback, `success=false`, `state_uncertain=true` | Compensation failed or may have partially applied | Reuse the recorded failed Rollback; do not rerun compensation automatically | Inspect the original Action effect and compensation state; perform a separately approved repair if required |
| Completed Rollback, `success=false`, `state_uncertain=false` | The Action result declared no mutation, so the failed compensation is not evidence of an outstanding mutation | Reuse the recorded Rollback outcome | Verify the `changed=false` contract and close the incident when other invariants hold |
| Claimed Operation taken over by a newer generation, `REQUIRE_LOCAL_STATE`, no same-process result cache | Previous callback may have executed before interruption | Record an uncertain outcome; do not call the stateful callback again | Reconcile using application-specific evidence |
| Completed Action with `REUSE_RESULT` | Policy explicitly permits result reuse across Runtime restarts | Reuse only when the callback is read-only, deterministic, or protected by durable downstream deduplication | Confirm the action registration and policy still satisfy that prerequisite |

`changed=false` is a meaningful callback contract, not a value that an
operator may add to a persisted result after the fact. Missing or malformed
`changed` is not equivalent to `false`.

## 4. Operator workflow

### Step 1 - Contain

- Stop or pause the affected workflow and prevent concurrent operators from
  launching a second correction.
- Record the cycle ID, tenant scope, parent Stage key, Action/Rollback name,
  idempotency key, active generation, and error/evidence identifiers.
- Preserve application logs and downstream system references before taking
  further action.

### Step 2 - Preserve and validate durable evidence

- Take a supported SQLite backup before investigation or corrective work.
- Run the repository's replay database readiness check (`check_database`) on
  the relevant database or restored copy.
- Inspect the Operation, parent Stage, Action-plan manifest, result envelope,
  and integrity status using read-only tooling.
- Confirm the row is completed or claimed, its attempt count, generation,
  operation kind, parent Action key (for Rollback), and `state_uncertain`
  value.
- Do not repair an integrity failure by changing JSON, digest, status, owner,
  or generation columns manually.

### Step 3 - Establish actual Runtime state

- Identify the Runtime instance and the state domain affected by the Action:
  Runtime context stack, Policy rules, Memory view, or an application-owned
  resource.
- Compare the current state with an authoritative source of truth, durable
  snapshot, or independently verifiable downstream record.
- For a failed callback, assume partial mutation is possible until evidence
  rules it out.
- For a failed Rollback, inspect both the original Action effect and the
  compensation. A failed compensation is not equivalent to a successful
  rollback.
- If no authoritative state or verifiable evidence exists, retain the
  fail-closed status and escalate to the owner of that state domain.

### Step 4 - Select a controlled correction

- If authoritative state can be restored, use the owning subsystem's supported
  restore/reconciliation procedure.
- If a new corrective mutation is needed, approve it as a new operation with a
  distinct parent Stage and idempotency key. Preserve the original completed
  Action and Rollback records unchanged.
- Require durable deduplication from any external system that owns the
  corrected side effect.
- Record the operator, approval, reason, evidence references, before/after
  state, and the new operation identity.
- Do not call the original stateful callback again merely because the
  Runtime restarted or its in-memory state is empty.

### Step 5 - Verify and resume

- Verify the post-correction state against the authoritative invariant.
- Verify that the original Operation and Rollback rows remain unchanged and
  integrity-valid.
- Verify the parent workflow's current Stage and Replay Claim generation.
- Resume only after the state owner and operator agree that the required
  invariant has been restored.
- Retain the incident and reconciliation evidence according to the
  application's operational retention policy.

## 5. SH-3 implementation boundary

The current built-in `SystemOptimizer` actions include:

- `reduce_context_depth`: changes the in-memory Runtime context stack and
  defaults to `REQUIRE_LOCAL_STATE`.
- `simplify_policy`: changes in-memory Policy rules and defaults to
  `REQUIRE_LOCAL_STATE`.
- `compress_memory`: produces a derived memory view and uses
  `REUSE_RESULT`; it is not a durable MemoryCore snapshot.

The built-in `SelfHealingCore` `rebuild_context` strategy clears the
in-memory `ContextManager` stack. A passed idempotency key is validation and
logging metadata for `ContextManager.clear`; it is not a durable deduplication
registry.

The current code does not provide a universal operator API that can reconstruct
arbitrary Runtime or application-owned state from an Operation result. Do not
claim that the Operation Ledger itself restores that state.

## 6. Escalation criteria

Escalate to the owner of the affected state domain when:

- `changed` is absent, malformed, or unknown;
- a callback or Rollback failed after it may have mutated state;
- current Runtime state differs from the authoritative source;
- no authoritative source exists to establish the actual state;
- a completed result has an integrity/readiness failure;
- a correction would repeat an external side effect without a durable
  downstream idempotency contract.

A workflow that cannot be reconciled safely must remain blocked rather than
being retried blindly.

## 7. Validation coverage

P3-2F-D validation was completed in tests/kernel/test_persistent_optimizer_action_ledger.py (11 tests passed) and covers:

- completed `REQUIRE_LOCAL_STATE` Action results with `changed=true`,
  `changed=false`, and missing/unknown `changed` after Runtime restart;
- no callback re-execution for a completed Operation;
- no automatic re-execution of a completed failed Action or failed Rollback
  after generation takeover;
- preservation of the original completed Operation rows, attempts, and
  generation during replay/reconciliation.

This runbook documents operator decisions. It does not claim that a
human-operated repair is automatically enforced by SH-3.