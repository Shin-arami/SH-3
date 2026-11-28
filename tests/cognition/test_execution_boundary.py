from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from cognition.contracts import (
    CognitiveContext,
    CognitiveDecision,
    CognitiveGoal,
    CognitiveLifecycleState,
    CognitivePlan,
)
from cognition.decision_boundary import CognitiveDecisionBoundary
from cognition.execution_boundary import CognitiveExecutionBoundary
from cognition.policy_boundary import CognitivePolicyEvaluation
from runtime.execution import ExecutionRequest, ExecutionState
from runtime.execution_engine import ExecutionOutcome, RuntimeExecutionEngine

NOW = datetime(2026, 10, 5, 0, 0, tzinfo=UTC)


def _goal() -> CognitiveGoal:
    return CognitiveGoal.create("prepare release", created_at=NOW, correlation_id="corr-1", trace_id="trace-1", tenant_id="tenant-1")


def _contracts() -> tuple[CognitiveGoal, CognitivePlan, CognitivePolicyEvaluation, CognitiveDecision, CognitiveContext]:
    goal = _goal()
    context = CognitiveContext.create(goal.goal_id, correlation_id=goal.correlation_id, trace_id=goal.trace_id, tenant_id=goal.tenant_id)
    plan = CognitivePlan.create(goal, ("op.release", "op.review"), created_at=NOW, correlation_id=goal.correlation_id, trace_id=goal.trace_id, tenant_id=goal.tenant_id)
    evaluation = CognitivePolicyEvaluation.create(goal, plan, allowed=True, context=context, created_at=NOW, reason="execution approved")
    decision = CognitiveDecisionBoundary().decide(goal, plan, context=context, policy_evaluation=evaluation, created_at=NOW)
    return goal, plan, evaluation, decision, context


class FakeExecutionBackend:
    def __init__(self, outcome: ExecutionOutcome) -> None:
        self.request: ExecutionRequest | None = None
        self.outcome = outcome

    def execute(self, request: ExecutionRequest, operation: Any = None) -> ExecutionOutcome:
        self.request = request
        return self.outcome


def _outcome(request_id: str = "exec-1", success: bool = True, state: ExecutionState = ExecutionState.COMPLETED) -> ExecutionOutcome:
    return ExecutionOutcome(execution_id=request_id, success=success, state=state, result={"ok": success})


def test_execution_boundary_creates_traceable_request() -> None:
    goal, plan, evaluation, decision, context = _contracts()
    backend = FakeExecutionBackend(_outcome())
    boundary = CognitiveExecutionBoundary(backend)

    outcome = boundary.execute(goal, plan, evaluation, decision, context=context, operation="op.release", created_at=NOW)

    assert outcome.execution_id == "exec-1"
    assert backend.request is not None
    assert backend.request.causation_id == decision.decision_id
    assert backend.request.correlation_id == decision.correlation_id
    assert backend.request.trace_id == decision.trace_id
    assert backend.request.tenant_id == decision.tenant_id
    assert backend.request.operation == "op.release"
    assert backend.request.payload["policy_evaluation_id"] == evaluation.evaluation_id


def test_execution_boundary_is_deterministic_for_identical_inputs() -> None:
    goal, plan, evaluation, decision, context = _contracts()
    first_backend = FakeExecutionBackend(_outcome("a"))
    second_backend = FakeExecutionBackend(_outcome("b"))
    first = CognitiveExecutionBoundary(first_backend)
    second = CognitiveExecutionBoundary(second_backend)
    first.execute(goal, plan, evaluation, decision, context=context, operation="op.release", created_at=NOW)
    second.execute(goal, plan, evaluation, decision, context=context, operation="op.release", created_at=NOW)
    assert first_backend.request is not None
    assert second_backend.request is not None
    assert first_backend.request.execution_id == second_backend.request.execution_id


def test_execution_boundary_requires_allowed_policy() -> None:
    goal, plan, _evaluation, decision, context = _contracts()
    denied = CognitivePolicyEvaluation.create(goal, plan, allowed=False, context=context, created_at=NOW, reason="denied")
    decision = CognitiveDecision.create(goal, plan.steps, selected_option=plan.steps[0], lifecycle_state=CognitiveLifecycleState.COMPLETED, causation_id=denied.evaluation_id, correlation_id=denied.correlation_id, trace_id=denied.trace_id, tenant_id=denied.tenant_id, created_at=NOW)
    with pytest.raises(ValueError, match="allow execution"):
        CognitiveExecutionBoundary(FakeExecutionBackend(_outcome())).execute(goal, plan, denied, decision, context=context, created_at=NOW)


def test_execution_boundary_requires_selected_decision() -> None:
    goal, plan, evaluation, _, context = _contracts()
    unresolved = CognitiveDecisionBoundary(lambda _: None).decide(goal, plan, context=context, policy_evaluation=evaluation, created_at=NOW)
    with pytest.raises(ValueError, match="select an option"):
        CognitiveExecutionBoundary(FakeExecutionBackend(_outcome())).execute(goal, plan, evaluation, unresolved, context=context, created_at=NOW)


def test_execution_boundary_rejects_broken_policy_causation() -> None:
    goal, plan, evaluation, _decision, context = _contracts()
    broken = CognitiveDecision.create(goal, plan.steps, selected_option=plan.steps[0], causation_id=plan.plan_id, correlation_id=evaluation.correlation_id, trace_id=evaluation.trace_id, tenant_id=evaluation.tenant_id, created_at=NOW)
    with pytest.raises(ValueError, match="causation_id"):
        CognitiveExecutionBoundary(FakeExecutionBackend(_outcome())).execute(goal, plan, evaluation, broken, context=context, created_at=NOW)


def test_execution_boundary_runs_real_runtime_engine() -> None:
    goal, plan, evaluation, decision, context = _contracts()
    engine = RuntimeExecutionEngine()
    engine.register_operation("op.release", lambda payload: {"goal_id": payload["goal_id"], "executed": True})
    outcome = CognitiveExecutionBoundary(engine).execute(
        goal, plan, evaluation, decision, context=context, operation="op.release", created_at=NOW
    )

    assert outcome.success
    assert outcome.state is ExecutionState.COMPLETED
    assert outcome.result == {"goal_id": goal.goal_id, "executed": True}
    assert outcome.snapshot is not None
    assert outcome.snapshot.causation_id == decision.decision_id
    assert outcome.snapshot.correlation_id == decision.correlation_id
    assert outcome.snapshot.trace_id == decision.trace_id
    assert outcome.snapshot.tenant_id == decision.tenant_id
