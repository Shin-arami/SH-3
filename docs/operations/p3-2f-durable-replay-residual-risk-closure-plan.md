# P3-2F - Durable Replay Residual Risk Closure Plan

## 1. Audit Baseline

- Repository: Shin-arami/SH-3
- Branch: v2.2-development
- Baseline commit: 8928c2ed11ff26e6e01bb63bc081f4e4bd3a39bb
- Previous audit: P3-2E Contract to Implementation Mapping
- Scope: P3-1A through P3-2E residual-risk closure
- Production policy: no production behavior changes until a concrete gap is demonstrated by a reproducible test or a required delivery guarantee.

This document is a risk assessment and implementation plan. It does not claim that the planned P3-2F tests have already passed.

## 2. Current Verified Findings

### 2.1 External Side-Effect Idempotency

P3-1A propagates the stable Recovery Stage idempotency key to the backend. P3-1B and P3-1C propagate derived keys to Optimizer Actions, Rollbacks, and supported context rebuild operations.

P3-2A and later phases persist local operation outcomes. They cannot atomically commit arbitrary external effects with the local SQLite ledger.

P3-2D includes a separate SQLite-backed fake downstream system. Its test demonstrates that a callback may execute twice while a downstream effect is applied once when the downstream system durably deduplicates the stable key.

This does not prove that every deployed custom backend or external service implements that contract.

Relevant references:
- docs/operations/p3-1a-recovery-backend-idempotency-contract.md
- docs/operations/p3-1b-optimizer-action-idempotency-contract.md
- docs/operations/p3-2d-recovery-execution-failure-matrix.md
- tests/kernel/test_persistent_recovery_replay_failure_matrix.py

### 2.2 Event Delivery and Outbox

P3-2D changes persistent Recovery terminal-event ordering so the Operation Ledger result and parent Stage are committed before event publication.

The current EventBus uses an EventQueue, RetryManager, and DeadLetterQueue in the running process. Its PublishResult reports delivery and retry state. EventBusPublisher returns that result to its caller.

RecoveryExecutionBoundary currently does not inspect the returned PublishResult. It catches publication exceptions after persistence and logs them. EventBus internally records delivery failures and applies its configured retry/dead-letter behavior.

There is no durable transactional event outbox in the reviewed Recovery path. A process can stop after Operation and Stage commits but before event publication. EventBus in-memory retry and dead-letter state does not establish cross-restart delivery.

Current contract: terminal events are best-effort notifications. Durable replay records remain authoritative.

Relevant references:
- kernel/recovery_execution_boundary.py
- infrastructure/event_bus/publisher.py
- infrastructure/event_bus/event_bus.py
- infrastructure/event_bus/delivery.py
- infrastructure/event_bus/retry.py
- infrastructure/event_bus/dead_letter.py
- docs/operations/p3-2c-durable-recovery-execution-replay-contract.md
- docs/operations/p3-2d-recovery-execution-failure-matrix.md

### 2.3 Runtime State Restoration

P3-2B defines REQUIRE_LOCAL_STATE and REUSE_RESULT policies.

A completed Action result does not imply that in-memory ContextManager, PolicyEngine, or MemoryCore state was restored after a Runtime restart.

The default REQUIRE_LOCAL_STATE policy fails closed when a changed or unknown local state cannot be proven restored. The result is marked state_uncertain and the callback is not blindly repeated. REUSE_RESULT is intended for results that are safe to reuse without claiming restoration of lost local state.

Existing tests cover a stateful Action failing closed after Runtime restart and a result-only Action reusing its stored result.

Relevant references:
- docs/operations/p3-2b-durable-optimizer-action-replay-contract.md
- kernel/system_optimizer.py
- tests/kernel/test_persistent_optimizer_action_ledger.py

### 2.4 SQLite Multiprocess Concurrency

The shared SQLite database adapter configures a connection timeout and PRAGMA busy_timeout. Mutations use BEGIN IMMEDIATE.

The Operation Store test includes an eight-thread concurrent begin test. It verifies that one caller claims the operation and the other callers receive ReplayOperationBusyError.

The P3-2D simulated SQLite lock case injects sqlite3.OperationalError. It verifies error propagation, but is not a real OS-level cross-process lock test.

At the P3-2F baseline, the Operation Store test file did not contain a multiprocessing or subprocess race test. P3-2F-A subsequently added Windows spawn-compatible tests for cross-process atomic begin, a real SQLite writer-lock timeout, and generation fencing against an old process owner. See tests/infrastructure/security/test_persistent_operation_store.py and the execution record below.

Relevant references:
- infrastructure/security/persistent_store.py
- infrastructure/security/persistent_operation_store.py
- tests/infrastructure/security/test_persistent_operation_store.py
- tests/kernel/test_persistent_recovery_replay_failure_matrix.py

## 3. Residual Risk Decisions

| ID | Risk | Current status | Decision |
|---|---|---|---|
| R-01 | External side-effect duplication | Stable key propagation and fake downstream dedupe are tested; real downstream conformance is deployment-specific | Add backend-specific conformance tests when a real backend is in scope. No generic exactly-once claim. |
| R-02 | Process-local fingerprint registry | P3-1C registry is process-local; persistent operation identities use the durable ledger | Keep legacy behavior bounded and documented. Do not claim P3-1C alone provides cross-restart dedupe. |
| R-03 | Runtime in-memory state restoration | Fail-closed behavior preserved; arbitrary Runtime state is not durably snapshotted; P3-2F-D reconciliation procedure and restart tests completed | Preserve fail-closed behavior. Use the P3-2F-D runbook; do not blindly replay stateful Actions. |
| R-04 | Operation/Stage separate commits | Intermediate Operation-completed / Stage-claimed state is recoverable through takeover and replay | Retain the recoverable two-step contract. Add process interruption tests where practical; do not force a larger transaction without evidence. |
| R-05 | Event delivery durability | No transactional outbox; current notification semantics remain best effort; P3-2F-B failure-result tests completed | Defer Outbox until durable event delivery is an explicit consumer requirement. Publisher-result, publisher-exception, and EventBus subscriber failure cases are tested. |
| R-06 | SQLite cross-process contention | Windows spawn-compatible Operation Store tests completed for concurrent begin, real writer-lock timeout, and generation fencing | Verified by the P3-2F-A multiprocess tests in test_persistent_operation_store.py. |
| R-07 | P3-2B validation evidence | Closed during P3-2E; focused, integration, static, and full-suite outputs recorded | Closed for the P3-2E audited baseline. |
| R-08 | Dedicated P3-1B validation record | Combined P3-1A/B/C validation exists; separate P3-1B full validation was not separately recorded | Retain as a historical evidence distinction, not a current implementation defect. |

## 4. P3-2F Work Packages

### P3-2F-A - Operation Store Multiprocess Verification

Priority: High.

Add deterministic tests using multiprocessing with the Windows spawn context. Every worker must create its own SQLiteReplayOperationStore and therefore its own SQLite connection.

Required scenarios:

1. Concurrent begin:
   - Prepare one valid parent Replay Claim and parent Stage.
   - Start multiple independent processes against the same database and same ReplayOperationKey.
   - Synchronize the workers so their begin calls overlap.
   - Expect exactly one CLAIMED result and the remaining same-generation callers to receive ReplayOperationBusyError.
   - Verify exactly one durable Operation row exists.
   - Unexpected sqlite3.OperationalError under the configured normal timeout is a failure requiring investigation.

2. Real writer-lock timeout:
   - A separate process opens the same database and holds BEGIN IMMEDIATE.
   - A second process attempts an Operation Store mutation with a deliberately short timeout.
   - Verify a real SQLite lock timeout is surfaced without a partial Operation row or corrupted transaction.
   - Release the lock through a finally-safe synchronization path.

3. Cross-process generation fencing:
   - Establish an unfinished Operation under generation N.
   - Transfer the parent Replay Claim to generation N+1.
   - Verify the new generation can take over the unfinished Operation.
   - Verify the stale generation cannot complete or overwrite the new owner's result.

Test requirements:
- Use top-level worker functions so Windows spawn can import them.
- Do not rely on shared in-process SQLite connection objects.
- Use Events, Queues, or Barriers to coordinate processes instead of arbitrary sleeps.
- Ensure every spawned process is joined and terminated safely on test failure.
- Keep test timeouts bounded and avoid timing-only correctness assertions.

Production code changes are not authorized by this plan. Make a code change only if a reproducible failure demonstrates an implementation defect.

### P3-2F-B - Event Publisher Failure Contract

Priority: Medium.

Add Recovery integration tests for both forms of delivery failure:

1. Publisher raises an exception after the durable Operation and Stage commits.
2. Publisher returns a PublishResult with delivered=false and a retry or dead-letter outcome, without raising.

Required invariants:
- The already committed Recovery Operation and Stage remain completed.
- The Recovery result is not converted into a persistence failure.
- The backend is not called again merely because notification delivery failed.
- A completed Operation restored by a later generation does not republish a terminal Recovery event.
- Delivery failure remains observable through the EventBus result, metrics, retry state, or dead-letter state.

This work package does not add a transactional outbox.

### P3-2F-C - External Backend Idempotency Conformance

Priority: High when a real external backend is selected.

For every production Recovery backend or Optimizer Action that performs non-idempotent external effects, require the following conformance checks:

1. Repeating the same key and same semantic input returns the same logical outcome.
2. Reusing the key with different semantic input is rejected.
3. Deduplication survives a process restart.
4. A timeout after the remote effect but before the response does not apply the effect twice when retried with the same key.
5. Concurrent calls with the same key do not apply the effect twice.
6. Deduplication retention is at least as long as the maximum replay and retry horizon.

A backend that only accepts the idempotency_key argument but does not persist and enforce it is not conformant for non-idempotent effects.

Do not invent a generic external adapter or claim downstream behavior without a concrete backend implementation and test environment.

### P3-2F-D - Runtime State Reconciliation

Priority: Medium.

Preserve REQUIRE_LOCAL_STATE as the default for stateful Actions.

Define an operator-facing reconciliation procedure that:
- Identifies the completed Operation and its stored Action result.
- Identifies the Runtime state that may be missing or uncertain.
- Reads the actual ContextManager, Policy, or Memory state from its authoritative source.
- Determines whether to restore, compensate, or manually reconcile that state.
- Records the reconciliation result as separate evidence.
- Does not overwrite a completed Operation row or blindly rerun the original stateful callback.

Add a state/reconciliation matrix for changed=true, changed=false, unknown result, failed callback, and failed rollback.

Do not add automatic generic Runtime snapshot restoration without a domain-specific state ownership and consistency design.

### P3-2F-E - Transactional Outbox Decision Gate

Priority: Conditional.

Do not implement an Outbox until event consumers require durable delivery across process restart.

If that requirement is approved, a separate design must define:
- Atomic insertion of the outbox record with the durable Recovery Operation outcome.
- Eligibility only after the parent Recovery Stage is completed.
- Stable event ID and canonical payload integrity.
- Durable claim lease, generation fencing, retry schedule, and dead-letter state.
- Delivery acknowledgment and recovery after worker interruption.
- Consumer-side idempotency by event ID.

An Outbox can provide durable at-least-once delivery, not universal exactly-once subscriber side effects. A consumer may apply an effect and stop before acknowledging delivery, so consumers must deduplicate.

A schema migration and readiness/backup/restore contract would be required. This is explicitly outside the first P3-2F test-only work package.

## 5. Execution Order

1. P3-2F-A: prove SQLite Operation Store behavior across independent OS processes.
2. P3-2F-B: verify delivery failure semantics without changing durable Recovery outcomes.
3. P3-2F-C: apply external backend conformance tests to each concrete backend when available.
4. P3-2F-D: document and test the operator reconciliation workflow.
5. P3-2F-E: decide whether durable event delivery is actually required; design Outbox only if approved.

## 6. Exit Criteria

P3-2F must not be declared complete until:

- Operation Store multiprocess claim and lock behavior are tested on Windows spawn.
- Stale generation fencing is verified across independent processes.
- Event Publisher failure results are covered without altering committed Recovery outcomes.
- Real backend conformance is either verified for each in-scope integration or explicitly recorded as an external deployment obligation.
- Runtime state reconciliation steps are documented with clear fail-closed boundaries.
- Outbox is explicitly accepted as deferred or separately approved with its schema and consumer contract.
- Ruff, Mypy, focused tests, full pytest, and git diff checks pass for any changed code.

No production code, database schema, or runtime behavior is changed by this planning document.

P3-2F status: execution and verification complete for the applicable scope; see the execution record dated 2026-11-26.

## Execution record - 2026-11-26

### Work package outcomes

- **A - VERIFIED:** Added cross-process Operation Store tests for atomic begin, SQLite writer-lock timeout, and generation fencing. The complete Operation Store test file passed with 22 tests.
- **B - VERIFIED:** Added Recovery failure tests for unsuccessful publication results, publisher exceptions, and EventBus subscriber failures after durable commit. The complete Recovery failure matrix passed with 12 tests.
- **C - NOT APPLICABLE:** No concrete external Recovery Backend is currently wired into the standard SH-3 recovery path. Do not introduce a fake production backend. Require backend-specific idempotency and failure-conformance tests when a real external backend is introduced.
- **D - VERIFIED:** Added Runtime State reconciliation tests covering changed, unchanged, and unknown state after restart, plus completed failed Action and Rollback replay. The complete optimizer Action Ledger test file passed with 11 tests.
- **E - DEFERRED:** Transactional Outbox implementation is deferred. Current event delivery is best-effort, and no concrete downstream consumer requirement for durable at-least-once delivery has been established. Reassess when such a requirement exists.

### Runtime State operations

The operational procedure is documented in:

`docs/operations/p3-2f-runtime-state-reconciliation-runbook.md`

The procedure preserves fail-closed behavior when Runtime state cannot be authoritatively reconciled. Durable Operation records must not be treated as proof that external or in-memory Runtime state was restored.

### SQLite Backup and Restore test correction

The semantic source contract test now explicitly closes its SQLite initialization connection before capturing the source database byte baseline. This makes WAL checkpoint timing deterministic for the byte-preservation assertion.

No production implementation code was changed for this correction.

### Final validation evidence

- Focused A/B/D integrated test set: 51 passed.
- Original-order Backup/Restore reproduction set: 385 passed.
- Complete SH-3 test suite: 1,424 passed in 95.03 seconds.
- Ruff: all checks passed on four modified test files.
- Mypy: no issues found in four source files.
- `git diff --check`: passed; only LF-to-CRLF working-copy warnings were reported.

### Final assessment

P3-2F execution and verification are complete for the applicable scope.

A, B, and D are verified. C has no applicable concrete external backend in the current standard wiring. E remains an explicit architectural decision to defer Outbox implementation pending a demonstrated durable-delivery requirement.

No production code or database schema changes were made. All implementation changes in this work package are test additions or test-harness corrections, accompanied by operational documentation.

This record does not claim that external side effects are globally idempotent or that Runtime state is automatically restored by durable replay records. Those boundaries remain explicit operational constraints.
