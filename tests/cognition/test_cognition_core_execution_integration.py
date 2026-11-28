from __future__ import annotations

from datetime import UTC, datetime

from cognition.contracts import (
    CognitiveContext,
    CognitiveGoal,
    CognitiveLifecycleState,
    CognitivePlan,
    CognitiveResultStatus,
)
from cognition.core import CognitionCore
from cognition.execution_boundary import CognitiveExecutionBoundary
from cognition.policy_boundary import CognitivePolicyBoundary, CognitivePolicyEvaluation
from runtime.execution import ExecutionRequest, ExecutionState
from runtime.execution_engine import ExecutionOperation, ExecutionOutcome, RuntimeExecutionEngine

NOW = datetime(2026, 10, 5, 0, 0, tzinfo=UTC)


class StubExecutionBackend:
    def __init__(self, outcome: ExecutionOutcome) -> None:
        self.outcome = outcome
        self.calls = 0
        self.request: ExecutionRequest | None = None

    def execute(self, request: ExecutionRequest, operation: ExecutionOperation | None = None) -> ExecutionOutcome:
        self.calls += 1
        self.request = request
        return self.outcome


def _core(backend: StubExecutionBackend) -> tuple[CognitionCore, StubExecutionBackend]:
    return CognitionCore(execution_boundary=CognitiveExecutionBoundary(backend)), backend


def test_execute_contract_maps_runtime_success_to_cognitive_result() -> None:
    backend = StubExecutionBackend(ExecutionOutcome("exec-success", True, ExecutionState.COMPLETED, result={"released": True}))
    cognition, backend = _core(backend)

    result = cognition.execute_contract("prepare release", operation="op.release", created_at=NOW)

    assert backend.calls == 1
    assert result.status is CognitiveResultStatus.SUCCESS
    assert result.lifecycle_state is CognitiveLifecycleState.COMPLETED
    assert result.output["execution"]["execution_id"] == "exec-success"
    assert result.causation_id == "exec-success"
    assert result.metadata["execution_id"] == "exec-success"
    assert result.output["decision"]["causation_id"] == result.output["policy"]["evaluation_id"]
    assert result.output["execution"]["snapshot"] is None


def test_execute_contract_maps_runtime_failure_to_cognitive_failure() -> None:
    backend = StubExecutionBackend(ExecutionOutcome("exec-failed", False, ExecutionState.FAILED, error=ValueError("runtime failed")))
    cognition, _ = _core(backend)

    result = cognition.execute_contract("prepare release", operation="op.release", created_at=NOW)

    assert result.status is CognitiveResultStatus.FAILURE
    assert result.lifecycle_state is CognitiveLifecycleState.FAILED
    assert result.error_type == "ValueError"
    assert result.error_message == "runtime failed"
    assert result.causation_id == "exec-failed"
    assert result.output["execution"]["state"] == "failed"


def test_execute_contract_preserves_trace_chain() -> None:
    backend = StubExecutionBackend(ExecutionOutcome("exec-trace", True, ExecutionState.COMPLETED, result="ok"))
    cognition, backend = _core(backend)
    result = cognition.execute_contract("prepare release", operation="op.release", created_at=NOW)

    policy = result.output["policy"]
    decision = result.output["decision"]
    execution = result.output["execution"]
    assert policy["correlation_id"] == decision["correlation_id"] == result.correlation_id
    assert policy["trace_id"] == decision["trace_id"] == result.trace_id
    assert policy["tenant_id"] == decision["tenant_id"] == result.tenant_id
    assert execution["execution_id"] == result.metadata["execution_id"]
    assert decision["causation_id"] == policy["evaluation_id"]
    assert backend.request is not None
    assert backend.request.causation_id == decision["decision_id"]


def test_execute_contract_does_not_execute_when_decision_is_unresolved() -> None:
    backend = StubExecutionBackend(ExecutionOutcome("exec-unresolved", True, ExecutionState.COMPLETED))
    cognition, backend = _core(backend)

    result = cognition.execute_contract("prepare release", policy=lambda _: None, created_at=NOW)

    assert result.status is CognitiveResultStatus.PARTIAL
    assert result.lifecycle_state is CognitiveLifecycleState.ACTIVE
    assert backend.calls == 0


def test_execute_contract_preserves_policy_denial_without_execution() -> None:
    class DenyPolicyBackend:
        def evaluate(
            self,
            goal: CognitiveGoal,
            plan: CognitivePlan,
            context: CognitiveContext,
        ) -> CognitivePolicyEvaluation:
            return CognitivePolicyEvaluation.create(
                goal,
                plan,
                allowed=False,
                context=context,
                created_at=NOW,
                reason="blocked",
            )

    backend = StubExecutionBackend(ExecutionOutcome("exec-denied", True, ExecutionState.COMPLETED))
    cognition = CognitionCore(
        policy_boundary=CognitivePolicyBoundary(DenyPolicyBackend()),
        execution_boundary=CognitiveExecutionBoundary(backend),
    )

    result = cognition.execute_contract("prepare release", created_at=NOW)

    assert result.status is CognitiveResultStatus.FAILURE
    assert result.error_type == "PolicyDenied"
    assert backend.calls == 0
    assert result.causation_id == result.output["policy"]["evaluation_id"]


def test_execute_contract_runs_real_runtime_execution() -> None:
    engine = RuntimeExecutionEngine()
    engine.register_operation("op.release", lambda payload: {"executed": payload["selected_option"]})
    cognition = CognitionCore(execution_boundary=CognitiveExecutionBoundary(engine))

    result = cognition.execute_contract("prepare release", operation="op.release", created_at=NOW)

    assert result.status is CognitiveResultStatus.SUCCESS
    assert result.lifecycle_state is CognitiveLifecycleState.COMPLETED
    assert result.output["execution"]["success"] is True
    assert result.output["execution"]["state"] == "completed"
    assert result.output["execution"]["result"] == {"executed": "prepare release"}
    assert result.causation_id == result.output["execution"]["execution_id"]
