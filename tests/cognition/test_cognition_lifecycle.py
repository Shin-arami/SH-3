from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cognition.contracts import (
    CognitiveContext,
    CognitiveGoal,
    CognitiveLifecycleState,
    CognitivePlan,
    CognitiveResult,
    CognitiveResultStatus,
)
from cognition.lifecycle import (
    CognitiveLifecycleStage,
    CognitiveLifecycleStateMachine,
)

NOW = datetime(2026, 10, 5, 0, 0, tzinfo=UTC)


def _goal() -> CognitiveGoal:
    return CognitiveGoal.create(
        "prepare release today",
        owner="test",
        created_at=NOW,
        correlation_id="corr-1",
        trace_id="trace-1",
        tenant_id="tenant-1",
    )


def _context(goal: CognitiveGoal) -> CognitiveContext:
    return CognitiveContext.create(
        goal.goal_id,
        correlation_id=goal.correlation_id,
        trace_id=goal.trace_id,
        tenant_id=goal.tenant_id,
    )


def test_lifecycle_starts_at_goal_created_and_is_deterministic() -> None:
    goal = _goal()
    first = CognitiveLifecycleStateMachine(goal, context=_context(goal))
    second = CognitiveLifecycleStateMachine(goal, context=_context(goal))

    assert first.stage is CognitiveLifecycleStage.GOAL
    assert first.state is CognitiveLifecycleState.CREATED
    assert first.to_dict()["lifecycle_id"] == second.to_dict()["lifecycle_id"]
    assert first.history == ()


def test_lifecycle_runs_full_execution_stage_sequence() -> None:
    goal = _goal()
    machine = CognitiveLifecycleStateMachine(goal, context=_context(goal))
    stages = [CognitiveLifecycleStage.PLANNING, CognitiveLifecycleStage.POLICY, CognitiveLifecycleStage.DECISION, CognitiveLifecycleStage.EXECUTION]

    for stage in stages:
        transition = machine.advance(stage, causation_id=f"{stage.value}-id", occurred_at=NOW)
        assert transition.to_stage is stage
        assert transition.to_state is CognitiveLifecycleState.ACTIVE

    transition = machine.advance(
        CognitiveLifecycleStage.RESULT,
        lifecycle_state=CognitiveLifecycleState.COMPLETED,
        causation_id="execution-1",
        occurred_at=NOW,
    )

    assert transition.to_stage is CognitiveLifecycleStage.RESULT
    assert machine.stage is CognitiveLifecycleStage.RESULT
    assert machine.state is CognitiveLifecycleState.COMPLETED
    assert [item.to_stage.value for item in machine.history] == [
        "planning", "policy", "decision", "execution", "result"
    ]


def test_lifecycle_allows_early_failure_at_result() -> None:
    goal = _goal()
    machine = CognitiveLifecycleStateMachine(goal, context=_context(goal))
    machine.advance(CognitiveLifecycleStage.PLANNING, causation_id="plan-1", occurred_at=NOW)
    machine.advance(CognitiveLifecycleStage.POLICY, causation_id="policy-1", occurred_at=NOW)
    transition = machine.advance(
        CognitiveLifecycleStage.RESULT,
        lifecycle_state=CognitiveLifecycleState.FAILED,
        causation_id="policy-1",
        occurred_at=NOW,
    )

    assert transition.from_stage is CognitiveLifecycleStage.POLICY
    assert machine.state is CognitiveLifecycleState.FAILED


def test_lifecycle_supports_suspend_and_resume() -> None:
    goal = _goal()
    machine = CognitiveLifecycleStateMachine(goal)
    machine.advance(CognitiveLifecycleStage.PLANNING, causation_id="plan-1", occurred_at=NOW)
    suspended = machine.transition_state(
        CognitiveLifecycleState.SUSPENDED,
        causation_id="pause-1",
        occurred_at=NOW,
    )
    resumed = machine.transition_state(
        CognitiveLifecycleState.ACTIVE,
        causation_id="resume-1",
        occurred_at=NOW,
    )

    assert suspended.to_state is CognitiveLifecycleState.SUSPENDED
    assert resumed.from_state is CognitiveLifecycleState.SUSPENDED
    assert machine.state is CognitiveLifecycleState.ACTIVE


def test_lifecycle_rejects_invalid_stage_transition() -> None:
    machine = CognitiveLifecycleStateMachine(_goal())

    with pytest.raises(ValueError, match="invalid lifecycle stage transition"):
        machine.advance(CognitiveLifecycleStage.DECISION, occurred_at=NOW)


def test_lifecycle_rejects_advancing_from_terminal_state() -> None:
    machine = CognitiveLifecycleStateMachine(_goal())
    machine.advance(CognitiveLifecycleStage.RESULT, lifecycle_state=CognitiveLifecycleState.FAILED, occurred_at=NOW)

    with pytest.raises(ValueError, match="invalid lifecycle stage transition"):
        machine.advance(CognitiveLifecycleStage.PLANNING, occurred_at=NOW)


def test_lifecycle_rejects_invalid_state_transition() -> None:
    machine = CognitiveLifecycleStateMachine(_goal())

    with pytest.raises(ValueError, match="invalid lifecycle state transition"):
        machine.transition_state(CognitiveLifecycleState.COMPLETED, occurred_at=NOW)


def test_lifecycle_validates_result_status_mapping() -> None:
    goal = _goal()
    machine = CognitiveLifecycleStateMachine(goal)
    result = CognitiveResult.create(
        goal,
        status=CognitiveResultStatus.SUCCESS,
        lifecycle_state=CognitiveLifecycleState.FAILED,
        created_at=NOW,
    )

    with pytest.raises(ValueError, match="status and lifecycle_state"):
        machine.finalize(result)


def test_lifecycle_finalize_validates_trace_identity() -> None:
    goal = _goal()
    machine = CognitiveLifecycleStateMachine(goal)
    other = CognitiveGoal.create(
        "other goal",
        owner="test",
        created_at=NOW,
        correlation_id=goal.correlation_id,
        trace_id=goal.trace_id,
        tenant_id=goal.tenant_id,
    )
    result = CognitiveResult.create(other, status=CognitiveResultStatus.SUCCESS, created_at=NOW)

    with pytest.raises(ValueError, match="goal_id"):
        machine.finalize(result)


def test_lifecycle_finalize_moves_execution_to_completed_result() -> None:
    goal = _goal()
    context = _context(goal)
    machine = CognitiveLifecycleStateMachine(goal, context=context)
    plan = CognitivePlan.create(goal, ("prepare release",), created_at=NOW)
    machine.advance(CognitiveLifecycleStage.PLANNING, causation_id=plan.plan_id, occurred_at=NOW)
    machine.advance(CognitiveLifecycleStage.POLICY, causation_id="policy-1", occurred_at=NOW)
    machine.advance(CognitiveLifecycleStage.DECISION, causation_id="decision-1", occurred_at=NOW)
    machine.advance(CognitiveLifecycleStage.EXECUTION, causation_id="decision-1", occurred_at=NOW)
    result = CognitiveResult.create(
        goal,
        status=CognitiveResultStatus.SUCCESS,
        created_at=NOW,
        causation_id="execution-1",
        correlation_id=goal.correlation_id,
        trace_id=goal.trace_id,
        tenant_id=goal.tenant_id,
    )

    transition = machine.finalize(result)

    assert transition.causation_id == "execution-1"
    assert machine.stage is CognitiveLifecycleStage.RESULT
    assert machine.state is CognitiveLifecycleState.COMPLETED


def test_lifecycle_context_must_match_goal() -> None:
    goal = _goal()
    other = CognitiveGoal.create("other", created_at=NOW)

    with pytest.raises(ValueError, match="context goal_id"):
        CognitiveLifecycleStateMachine(goal, context=CognitiveContext.create(other.goal_id))
