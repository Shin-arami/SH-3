# P3-2E - Contract to Implementation Mapping and Audit

## Audit baseline

- Repository: `Shin-arami/SH-3`
- Branch: `v2.2-development`
- Audited commit: `c650754ee881d8b37b97ec83c66a6940a7ed2964`
- Scope: P3-1A through P3-2D
- Audit mode: contract, implementation path, test path, recorded validation, and residual-risk traceability
- Production-code policy: this audit adds no production behavior and introduces no schema migration.

Validation entries below distinguish recorded results from unavailable evidence. A commit or a contract's suggested command is not, by itself, proof that a test or static check was executed successfully.

## 1. Contract-to-implementation mapping

| Part | Contract / commit | Guaranteed invariant or behavior | Production implementation | Corresponding tests | Production code changed? |
|---|---|---|---|---|---|
| P3-1A | `p3-1a-recovery-backend-idempotency-contract.md` / `2853a638fd79c168197485bccd3c812f93bc9779` | Persistent Recovery forwards the exact stable `ReplayStageKey.idempotency_key` to the backend; legacy non-persistent calls preserve the old signature. Backend capability is checked at boundary construction. | `kernel/recovery_execution_boundary.py`; `self_healing/core.py` | `tests/kernel/test_recovery_execution_boundary.py` | Yes |
| P3-1B | `p3-1b-optimizer-action-idempotency-contract.md` / same P3-1 commit | Optimizer derives deterministic child keys per Action and separate rollback keys; key fields propagate through normalized results and events; keyed rollback fails closed if callback cannot accept the key. | `kernel/system_optimizer.py`; `kernel/optimizer_update_boundary.py` | `tests/kernel/test_system_optimizer.py`; `tests/kernel/test_optimizer_update_boundary.py`; `tests/integration/test_p1_5_optimizer_action_execution.py` | Yes |
| P3-1C | `p3-1c-idempotency-collision-recovery-hardening-contract.md` / same P3-1 commit | Tenant-scoped parent-key fingerprint collision detection within one boundary instance; rollback failure uncertainty is surfaced; Recovery context clear forwards the key when supported. | `kernel/optimizer_update_boundary.py`; `kernel/system_optimizer.py`; `kernel/recovery_execution_boundary.py`; `self_healing/core.py`; `runtime/context_manager.py` | `tests/kernel/test_optimizer_update_boundary.py`; `tests/kernel/test_system_optimizer.py`; `tests/kernel/test_recovery_execution_boundary.py`; `tests/runtime/test_context_manager.py` | Yes |
| P3-2A | `p3-2a-durable-idempotency-ledger-contract.md` / `2475086d408b14fa90ceb566cfbf23d522c618ae` | Adds durable tenant-scoped Operation identity, input fingerprint collision rejection, Action/Rollback linkage, claimed→completed lifecycle, parent-generation fencing, canonical-result integrity, readiness validation, and backup/restore preservation. | `infrastructure/security/persistent_operation_store.py`; `infrastructure/security/persistent_replay_ops.py`; `infrastructure/security/persistent_replay_provision.py`; `infrastructure/security/persistent_replay_runtime.py` | `tests/infrastructure/security/test_persistent_operation_store.py` | Yes |
| P3-2B | `p3-2b-durable-optimizer-action-replay-contract.md` / `185f6a5e09be83efb7a5ae9a49c4fe6fa953c0c3` | Connects persistent Optimizer Action/Rollback execution to the ledger; persists an immutable Action-plan manifest; stores successful and failed outcomes; applies explicit cross-Runtime replay policy (`REQUIRE_LOCAL_STATE` / `REUSE_RESULT`); persistence errors propagate and prevent parent Stage finalization. | `infrastructure/security/persistent_operation_store.py`; `infrastructure/security/persistent_replay_ops.py`; `kernel/core.py`; `kernel/learning_optimizer_boundary.py`; `kernel/optimizer_update_boundary.py`; `kernel/persistent_factory.py`; `kernel/replay_execution_context.py`; `kernel/system_optimizer.py` | `tests/kernel/test_persistent_optimizer_action_ledger.py` | Yes |
| P3-2C | `p3-2c-durable-recovery-execution-replay-contract.md` / `866e3b5e58ca3eb4e5d9529ea2a0cdffecebe094` | Connects Recovery Execution to one durable Operation row; completed Operation is restored without backend re-execution; Operation is committed before parent Stage; existing P3-1 backend key remains unchanged; persistence errors propagate. | `kernel/recovery_execution_boundary.py`; `kernel/optimizer_healing_boundary.py`; `kernel/learning_feedback_loop.py`; `kernel/core.py` | `tests/kernel/test_persistent_recovery_execution_ledger.py`; `tests/kernel/test_recovery_execution_boundary.py`; `tests/kernel/test_optimizer_healing_boundary.py` | Yes |
| P3-2D | `p3-2d-recovery-execution-failure-matrix.md` / `c650754ee881d8b37b97ec83c66a6940a7ed2964` | For the Operation Ledger path, Recovery terminal events publish only after Operation and parent Stage commits; persistence failures suppress the event; publication failure does not undo committed state; failure/backup/restore/integrity cases are covered. | `kernel/recovery_execution_boundary.py` | `tests/kernel/test_persistent_recovery_replay_failure_matrix.py`; `tests/kernel/test_persistent_recovery_execution_ledger.py`; `tests/kernel/test_recovery_execution_boundary.py`; `tests/kernel/test_optimizer_healing_boundary.py` | Yes |

## 2. Recorded validation evidence

| Part | Focused / integration evidence | Full suite | Ruff | Mypy | Evidence status |
|---|---|---:|---|---|---|
| P3-1A | 19 focused Recovery-boundary tests; 40 tests in a related four-file set | 1,361 passed at that stage | Passed | Passed on 2 source files | Recorded for the P3-1A stage |
| P3-1B | 24 focused tests across `test_system_optimizer.py`, `test_optimizer_update_boundary.py`, and `test_p1_5_optimizer_action_execution.py` | No separate full-suite result recorded for P3-1B | No separate result recorded | No separate result recorded | Focused evidence only |
| P3-1A/B/C finalization | 7 final added tests passed; combined P3-1A/B/C commit | 1,373 passed (recorded as pre-final-fix full-suite result) | Passed | Passed on 5 source files | Recorded for combined P3-1A/B/C |
| P3-2A | 19 Store tests passed in final validation record | 1,392 passed | Passed | Passed | Recorded in project validation history |
| P3-2B | 7 focused tests passed; 41 tests passed in the adjacent durable replay / Recovery integration set | 1,414 passed in 61.18s | Passed | Passed; Mypy reported no issues in 12 source files | Validation evidence recorded during P3-2E; the adjacent set includes the P3-2B focused test file |
| P3-2C | 39 focused tests passed; 18 persistent restart tests passed | 1,405 passed | Passed | Passed on the relevant source/test set | Recorded in project validation history |
| P3-2D | 48 focused tests passed; 33 integration tests passed | 1,414 passed | Passed | Passed on 9 source/test files | Recorded in project validation history |

`git diff --check` was reported clean for P3-2A through P3-2D, apart from Git LF→CRLF working-copy warnings where noted. P3-1 finalization recorded `git diff --cached --check` success.

## 3. Residual-risk register

| ID | Residual risk / non-guarantee | Affected Parts | Audit interpretation |
|---|---|---|---|
| R-01 | SH-3 cannot atomically commit arbitrary external side effects and its SQLite replay row. A process may stop after the external effect but before the durable result commit. | P3-1A, P3-1B, P3-1C, P3-2A, P3-2B, P3-2C, P3-2D | Downstream system owning the effect must durably deduplicate the stable key, return the prior result for exact repeats, and reject conflicting input. No universal exactly-once claim. |
| R-02 | P3-1C parent-key fingerprint registry is process-local, not a durable cross-restart ledger. | P3-1C | Durable replay identity is supplied later by P3-2A/2B for supported persistent paths; do not describe P3-1C alone as cross-restart protection. |
| R-03 | A durable Action result does not restore in-memory Runtime, ContextManager, PolicyEngine, or MemoryCore state. | P3-2A, P3-2B | `REQUIRE_LOCAL_STATE` must fail closed when changed/unknown local state cannot be proven restored; `REUSE_RESULT` is only appropriate for a result-only/read-only/deterministic or otherwise durably deduplicated action. |
| R-04 | The Operation Ledger and parent Stage are separate commits. A crash between them leaves an Operation-completed / Stage-claimed recovery point. | P3-2B, P3-2C, P3-2D | Newer valid claim generation must restore the completed Operation and finish the Stage without rerunning the callback. |
| R-05 | Recovery terminal event publication has a final crash window after durable commits and before publish; there is no transactional outbox. | P3-2C, P3-2D | Event delivery is best effort, not exactly-once or at-least-once. Durable replay records are authoritative. |
| R-06 | P3-2D's SQLite lock case injects `sqlite3.OperationalError("database is locked")`; it is not an OS-level lock-contention stress test. | P3-2D | Treat it as deterministic error-propagation coverage, not proof of real multi-process lock behavior under stress. |
| R-07 | P3-2B validation gap was closed during P3-2E: 7 focused tests passed, the adjacent integration set passed 41 tests, the full suite passed 1,414 tests, Ruff passed, and Mypy reported no issues in 12 source files. | P3-2B | Validation evidence is now recorded for the audited baseline; rerun applicable checks after subsequent source changes. |
| R-08 | P3-1B had focused test evidence, but no separately recorded full-suite/Ruff/Mypy result for that sub-phase. The combined P3-1A/B/C finalization did record broader validation. | P3-1B | Preserve both facts; do not imply a dedicated P3-1B full validation run occurred. |

## 4. Audit conclusions

1. The P3-1A/B/C implementation is present in commit `2853a638fd79c168197485bccd3c812f93bc9779`; the commit changes 13 files across contracts, production code, and tests.
2. P3-2A adds the durable Operation Store and readiness/provision/runtime wiring; P3-2B integrates durable Action/Rollback execution and immutable Action plans.
3. P3-2C integrates Recovery Execution with the same Operation Ledger while preserving the P3-1A downstream Recovery key.
4. P3-2D corrects terminal-event ordering for the persistent Operation path and adds the failure matrix. It does not add an outbox or expand the exactly-once guarantee.
5. The previously identified P3-2B validation-record gap was closed during P3-2E: 7 focused tests passed, the adjacent durable replay / Recovery test set passed 41 tests, Ruff passed, Mypy reported no issues in 12 source files, and the full suite passed 1,414 tests.
6. This mapping is an audit baseline, not a claim that every possible external backend or multi-process deployment has been proven. The residual-risk register remains part of the contract.

## 5. Recommended validation commands

Run from `C:\projects\sh-3` with the project's configured `$Python` executable:

```powershell
Set-Location "C:\projects\sh-3"

# P3-2B focused contract
& $Python -m pytest -q tests\kernel\test_persistent_optimizer_action_ledger.py

# Adjacent durable replay / Recovery regression set
& $Python -m pytest -q `
    tests\infrastructure\security\test_persistent_operation_store.py `
    tests\kernel\test_persistent_optimizer_action_ledger.py `
    tests\kernel\test_persistent_recovery_execution_ledger.py `
    tests\kernel\test_persistent_recovery_replay_failure_matrix.py

# Static checks
& $Python -m ruff check infrastructure kernel tests

& $Python -m mypy `
    infrastructure\security\persistent_operation_store.py `
    infrastructure\security\persistent_replay_ops.py `
    infrastructure\security\persistent_replay_runtime.py `
    kernel\replay_execution_context.py `
    kernel\system_optimizer.py `
    kernel\learning_optimizer_boundary.py `
    kernel\optimizer_update_boundary.py `
    kernel\recovery_execution_boundary.py `
    kernel\optimizer_healing_boundary.py `
    kernel\learning_feedback_loop.py `
    kernel\core.py `
    tests\kernel\test_persistent_optimizer_action_ledger.py

# Full suite
& $Python -m pytest -q

# Working-tree / whitespace audit
git diff --check
git status --short --branch
```

Do not stage, commit, or push this audit document until its contents and the missing P3-2B validation evidence have been reviewed.
