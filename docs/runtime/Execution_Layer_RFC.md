# SH-3 Complete Edition v2.0 — Runtime / Execution Layer RFC

## 1. Purpose

Runtime / Execution Layer は、Kernel / Services が決定した実行要求を、決定論的・型安全・キャンセル可能・監視可能な実行単位として処理する。

Runtime は「何を実行するか」を決定しない。

責務は以下に限定する。

- Execution Request の受理
- Execution Lifecycle の管理
- Execution State の遷移
- 実行スケジューリング
- Cancellation / Timeout
- Failure propagation
- Resource cleanup
- Execution Event の発行
- Execution Evidence / Observability の生成

Planning、Decision、Policy、Learning、Self-Healing、Optimizer の意思決定ロジックは Runtime の責務外とする。

---

## 2. Architectural Position

```text
Application
    ↓
Deployment
    ↓
Kernel
    ↓
Services
    ↓
Runtime / Execution
    ↓
Infrastructure
    ↓
Foundation
```

Runtime は Services の下位実行基盤であり、Infrastructure の上位に位置する。

Runtime から上位層へ直接依存してはならない。

```text
Allowed:
Runtime → Infrastructure
Runtime → Foundation

Forbidden:
Runtime → Planner implementation
Runtime → LearningLoop implementation
Runtime → SelfHealingCore implementation
Runtime → Optimizer implementation
Runtime → Application implementation
```

上位層との連携は Protocol / Contract / Event を介して行う。

---

## 3. Core Concepts

### 3.1 ExecutionRequest

実行要求を表す immutable な値オブジェクト。

最低限以下を持つ。

```text
execution_id
operation
payload
priority
timeout
correlation_id
causation_id
trace_id
metadata
```

`execution_id` は Execution 単位の一意識別子とする。

---

### 3.2 Execution

1つの Execution Request に対応する実行コンテキスト。

Execution は以下を管理する。

```text
request
state
started_at
completed_at
result
error
attempt
trace_id
```

Execution 自体は実行戦略を決定しない。

---

### 3.3 ExecutionState

Execution Lifecycle の正式な状態。

```text
CREATED
QUEUED
RUNNING
COMPLETED
FAILED
CANCEL_REQUESTED
CANCELLED
TIMED_OUT
```

Terminal State:

```text
COMPLETED
FAILED
CANCELLED
TIMED_OUT
```

Terminal State から別の状態への遷移は禁止する。

---

## 4. State Transition Contract

正規遷移：

```text
CREATED
  ↓
QUEUED
  ↓
RUNNING
  ├─→ COMPLETED
  ├─→ FAILED
  ├─→ CANCEL_REQUESTED
  └─→ TIMED_OUT

CANCEL_REQUESTED
  └─→ CANCELLED
```

禁止：

```text
COMPLETED → RUNNING
COMPLETED → FAILED
FAILED → RUNNING
FAILED → COMPLETED
CANCELLED → RUNNING
TIMED_OUT → RUNNING
```

State transition は単一の Runtime authority によって管理する。

外部 component が Execution State を直接変更してはならない。

---

## 5. Execution Contract

Execution Engine は以下の概念的契約を持つ。

```python
class ExecutionEngine(Protocol):
    def submit(self, request: ExecutionRequest) -> ExecutionHandle: ...
    def execute(self, request: ExecutionRequest) -> ExecutionResult: ...
    def cancel(self, execution_id: str) -> bool: ...
    def get(self, execution_id: str) -> ExecutionSnapshot | None: ...
```

実際の API 名は既存 Runtime 実装との整合性確認後に確定する。

重要なのは以下の契約である。

- submit は Execution ID を返す
- execute は結果を返す
- cancel は idempotent である
- get は現在の snapshot を返す
- Execution Engine は thread safe である

---

## 6. ExecutionHandle

非同期 Execution を識別するための opaque handle。

Handle は Execution ID を公開してよいが、内部実装や worker/thread/future を公開してはならない。

```text
ExecutionHandle
    ↓
execution_id
```

上位層は worker implementation に依存しない。

---

## 7. Cancellation Contract

Cancellation は cooperative cancellation を基本とする。

```text
RUNNING
   ↓
CANCEL_REQUESTED
   ↓
worker observes cancellation
   ↓
cleanup
   ↓
CANCELLED
```

Cancellation Request 自体は Execution を即座に `CANCELLED` に変更してはならない。

実行中処理が終了し cleanup が完了した時点で `CANCELLED` とする。

Cancellation は idempotent とする。

```text
cancel(id)
cancel(id)
cancel(id)
```

複数回呼び出しても副作用を増加させない。

---

## 8. Timeout Contract

Timeout は Runtime が管理する。

Timeout 発生時：

```text
RUNNING
   ↓
TIMED_OUT
   ↓
cleanup
```

Timeout は通常の application exception と混同しない。

Timeout は Execution Lifecycle の terminal condition として記録する。

Timeout 発生後に worker が結果を生成しても、元 Execution を `COMPLETED` に戻してはならない。

Late result は破棄または別 evidence として記録する。

---

## 9. Failure Contract

Execution failure は以下を分離する。

```text
Execution Failure
├─ operation error
├─ timeout
├─ cancellation
├─ infrastructure error
└─ internal runtime error
```

Failure は exception object そのものを cross-layer contract として公開しない。

公開する情報：

```text
error_type
error_message
execution_id
trace_id
correlation_id
attempt
timestamp
```

機密情報・credential・内部 stack trace を Event payload に無制限に格納してはならない。

---

## 10. Retry Boundary

Retry は Runtime の暗黙動作にしない。

Retry を行う場合は明示的な Execution Policy / Retry Policy によって制御する。

```text
Execution
    ↓
Failure
    ↓
Retry Policy
    ├─ retry
    └─ terminal failure
```

Retry 回数、backoff、retryable error は contract として明示する。

無限 retryは禁止。

---

## 11. Scheduling Contract

Scheduler は deterministic behavior を優先する。

同一 priority の Execution については stable ordering を使用する。

基本順序：

```text
priority
→ creation sequence
→ execution_id
```

Scheduler は business priority の意味を定義しない。

Priority value の解釈は上位 contract によって決定する。

---

## 12. Concurrency Contract

Runtime は thread safe であることを必須とする。

以下は race condition を起こしてはならない。

```text
submit
cancel
timeout
complete
fail
snapshot
shutdown
```

同一 Execution に対する競合：

```text
complete()
cancel()
timeout()
fail()
```

は単一の state transition authority によって deterministic に解決する。

---

## 13. Resource Cleanup Contract

Execution 終了時には必ず cleanup を実行する。

対象：

```text
worker
future
queue entry
temporary resource
execution context
subscription
timer
```

Terminal state への遷移と cleanup の関係を明示する。

```text
execution termination
        ↓
cleanup
        ↓
terminal snapshot
        ↓
completion event
```

cleanup failure は元の execution result と別に記録する。

---

## 14. Shutdown Contract

Runtime shutdown は graceful shutdown を基本とする。

```text
RUNNING
  ↓
STOP_REQUESTED
  ↓
stop accepting new execution
  ↓
wait / cancel according to policy
  ↓
cleanup
  ↓
STOPPED
```

Shutdown 後に新しい Execution を受理してはならない。

Shutdown は idempotent とする。

---

## 15. Event Contract

Runtime は Lifecycle を EventBus に公開する。

最低限：

```text
RuntimeExecutionSubmitted
RuntimeExecutionStarted
RuntimeExecutionCompleted
RuntimeExecutionFailed
RuntimeExecutionCancelled
RuntimeExecutionTimedOut
RuntimeExecutionCleanupFailed
```

Event payload には最低限：

```text
execution_id
correlation_id
causation_id
trace_id
timestamp
state
attempt
```

を含める。

Event は Runtime 内部状態の代替ではない。

Runtime State が source of truth であり、Event は state transition の observable record とする。

---

## 16. Propagation Contract

Runtime は EventPropagationContext を利用する。

```text
Kernel
  ↓
Service
  ↓
Runtime
  ↓
Execution
```

この chain で以下を維持する。

```text
correlation_id
trace_id
causation_id
tenant_id
```

Execution event の causation は直前の parent event または execution event に由来する。

---

## 17. Evidence Contract

Execution は production audit に必要な evidence を生成可能であること。

最低限：

```text
execution_id
operation
state
started_at
completed_at
duration
attempt
result status
error information
trace_id
correlation_id
```

Evidence は mutable runtime state と分離する。

Execution snapshot の integrity verification が必要な場合は、既存 `EvidenceRecord` / `EvidenceStore` contract を利用する。

Runtime が独自の別証跡形式を作ってはならない。

---

## 18. Observability Contract

Runtime は以下を観測可能にする。

### Logging

```text
execution submitted
execution started
execution completed
execution failed
execution cancelled
execution timed out
cleanup failed
```

### Metrics

最低限候補：

```text
execution_total
execution_success_total
execution_failure_total
execution_cancelled_total
execution_timeout_total
execution_duration
execution_active
execution_queue_depth
```

### Tracing

Execution ID と Trace ID を関連付ける。

```text
trace_id
  └─ execution_id
       ├─ submit
       ├─ start
       ├─ operation
       └─ completion
```

---

## 19. Determinism

Runtime の observable behavior は可能な限り deterministic であること。

対象：

- state transition
- queue ordering
- retry decision
- cancellation result
- shutdown result
- event ordering
- snapshot representation

Wall-clock timestamp 自体は deterministic ではないため、business decision に使用してはならない。

---

## 20. Idempotency

以下は idempotent であることを要求する。

```text
cancel(execution_id)
shutdown()
get(execution_id)
register identical execution metadata
```

特に retry / duplicate event によって Execution が二重完了しないことを保証する。

---

## 21. Boundary Rules

Runtime が直接依存してはならないもの：

```text
Planner implementation
Memory implementation
LearningLoop implementation
SelfHealingCore implementation
Optimizer implementation
LLM implementation
Agent implementation
Tool implementation
```

Runtime が依存してよいもの：

```text
Foundation types
Foundation exceptions
Infrastructure EventBus
Infrastructure tracing
Infrastructure metrics
Infrastructure logging
Infrastructure storage
Execution contracts
```

---

## 22. Testability

Execution operation は injectable にする。

Runtime test では実際の OS process、network、external API を必須としない。

最低限以下を mock / fake / deterministic test double で置換可能とする。

```text
clock
scheduler
worker
event publisher
storage
metrics
tracer
logger
```

---

## 23. Test Specification

### T1 — Lifecycle

- CREATED → QUEUED
- QUEUED → RUNNING
- RUNNING → COMPLETED
- RUNNING → FAILED
- RUNNING → CANCEL_REQUESTED → CANCELLED
- RUNNING → TIMED_OUT
- terminal state からの再遷移拒否

### T2 — Submission

- unique execution ID
- duplicate ID handling
- invalid request rejection
- immutable request behavior

### T3 — Execution

- successful execution
- execution failure
- exception normalization
- result preservation
- completion timestamp

### T4 — Cancellation

- queued cancellation
- running cancellation
- repeated cancellation
- cancellation after completion
- cancellation after failure
- cancellation after timeout

### T5 — Timeout

- timeout before execution
- timeout during execution
- timeout race with completion
- timeout race with cancellation
- late result handling

### T6 — Concurrency

- concurrent submit
- concurrent cancel
- concurrent snapshot
- completion/cancellation race
- completion/timeout race
- shutdown/submit race

### T7 — Scheduler

- priority ordering
- stable ordering
- deterministic ordering
- queue depth
- queue rejection

### T8 — Events

- Submitted event
- Started event
- Completed event
- Failed event
- Cancelled event
- TimedOut event
- CleanupFailed event
- propagation context preservation
- causation chain
- event ordering

### T9 — Evidence

- successful execution evidence
- failed execution evidence
- timeout evidence
- cancellation evidence
- deterministic serialization
- integrity verification
- duplicate evidence handling

### T10 — Shutdown

- graceful shutdown
- shutdown with queued work
- shutdown with running work
- repeated shutdown
- submission after shutdown rejection
- cleanup verification

### T11 — Failure Isolation

- operation failure does not corrupt Runtime
- event publication failure does not corrupt execution state
- metrics failure does not corrupt execution
- logging failure does not corrupt execution
- evidence registration failure is isolated according to policy
- cleanup failure is separately recorded

### T12 — Static / Type Validation

```text
Ruff
mypy --explicit-package-bases
pytest
pytest -W error::DeprecationWarning
```

Runtime implementation must not introduce new warnings.

---

## 24. Acceptance Criteria

Runtime / Execution Layer implementation is considered complete only when:

1. All lifecycle transitions are explicitly defined.
2. Invalid transitions are rejected deterministically.
3. Cancellation is idempotent.
4. Timeout is deterministic and terminal.
5. Retry is explicitly bounded.
6. Concurrent state changes are thread safe.
7. Resource cleanup is guaranteed.
8. Shutdown is idempotent.
9. Runtime events preserve propagation context.
10. Execution evidence is traceable and integrity-verifiable.
11. Infrastructure failures cannot silently corrupt execution state.
12. Runtime has no direct dependency on higher-level cognitive/service implementations.
13. All execution components are replaceable through contracts.
14. Unit and integration tests cover lifecycle races.
15. Ruff passes.
16. mypy passes.
17. Full existing regression suite remains green.

---

## 25. Implementation Order

Implementation must follow this order:

```text
1. Execution Types / Contracts
        ↓
2. Execution State Machine
        ↓
3. Execution Context / Snapshot
        ↓
4. Execution Engine
        ↓
5. Scheduler
        ↓
6. Cancellation / Timeout
        ↓
7. Resource Cleanup
        ↓
8. EventBus Integration
        ↓
9. Evidence / Observability
        ↓
10. Shutdown
        ↓
11. Unit Tests
        ↓
12. Integration Tests
        ↓
13. Full Regression
```

No Cognitive / Agent implementation should be added before this layer reaches the acceptance criteria.

---

## 26. v2.2 Design Principle

The Runtime / Execution Layer is the execution authority of SH-3.

```text
Kernel decides WHAT should happen.
Services decide WHY / WHICH strategy should be used.
Runtime decides HOW the execution lifecycle is safely performed.
Infrastructure provides the underlying mechanisms.
```

Runtime must remain deterministic, replaceable, observable, testable, and independent from higher-level cognition.
