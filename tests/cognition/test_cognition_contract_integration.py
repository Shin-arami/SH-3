from __future__ import annotations

from datetime import UTC, datetime

from cognition.contracts import (
    CognitiveContext,
    CognitiveGoal,
    CognitiveLifecycleState,
    CognitiveResultStatus,
)
from cognition.core import CognitionCore, CognitiveState
from cognition.planner import Planner
from cognition.planning_boundary import CognitivePlanningBoundary

NOW = datetime(2026, 10, 4, 0, 0, tzinfo=UTC)


def test_existing_cognition_state_api_remains_compatible() -> None:
    cognition = CognitionCore()
    state = cognition.create_state("prepare release notes")

    assert isinstance(state, CognitiveState)
    assert state.goal == "prepare release notes"
    assert state.to_dict()["goal"] == state.goal


def test_core_creates_deterministic_typed_goal() -> None:
    cognition = CognitionCore()

    first = cognition.create_goal("prepare release", owner="test", created_at=NOW)
    second = cognition.create_goal("prepare release", owner="test", created_at=NOW)

    assert first == second
    assert first.goal_id == second.goal_id
    assert first.trace_id == second.trace_id


def test_plan_contract_uses_replaceable_planning_boundary() -> None:
    goal = CognitiveGoal.create("prepare release", owner="test", created_at=NOW)
    cognition = CognitionCore(planning_boundary=CognitivePlanningBoundary(Planner(chunk_size=2)))

    plan = cognition.plan_contract(goal, created_at=NOW)

    assert plan.goal_id == goal.goal_id
    assert plan.steps == ("prepare release",)
    assert plan.trace_id == goal.trace_id


def test_create_context_inherits_goal_trace_fields() -> None:
    cognition = CognitionCore()
    goal = cognition.create_goal(
        "prepare release",
        owner="test",
        created_at=NOW,
        correlation_id="corr-1",
        trace_id="trace-1",
        tenant_id="tenant-1",
    )

    context = cognition.create_context(goal, values={"source": "test"}, causation_id="cause-1")

    assert context.goal_id == goal.goal_id
    assert context.correlation_id == "corr-1"
    assert context.causation_id == "cause-1"
    assert context.trace_id == "trace-1"
    assert context.tenant_id == "tenant-1"


def test_run_contract_returns_typed_success_with_complete_trace_chain() -> None:
    cognition = CognitionCore(planning_boundary=CognitivePlanningBoundary(Planner(chunk_size=2)))
    goal = cognition.create_goal(
        "prepare release today",
        owner="test",
        created_at=NOW,
        correlation_id="corr-1",
        trace_id="trace-1",
        tenant_id="tenant-1",
    )

    result = cognition.run_contract(goal, policy=lambda options: options[-1], created_at=NOW)

    assert result.status is CognitiveResultStatus.SUCCESS
    assert result.lifecycle_state is CognitiveLifecycleState.COMPLETED
    assert result.goal_id == goal.goal_id
    assert result.correlation_id == goal.correlation_id
    assert result.trace_id == goal.trace_id
    assert result.tenant_id == goal.tenant_id
    output = result.output
    assert output["goal"]["goal_id"] == goal.goal_id
    assert output["plan"]["goal_id"] == goal.goal_id
    assert output["decision"]["selected_option"] == "today"
    assert output["state"]["goal_id"] == goal.goal_id
    assert result.causation_id == output["decision"]["decision_id"]


def test_run_contract_rejects_invalid_policy_without_raising() -> None:
    cognition = CognitionCore(planning_boundary=CognitivePlanningBoundary(Planner(chunk_size=2)))
    goal = cognition.create_goal("prepare release", created_at=NOW)

    result = cognition.run_contract(goal, policy=lambda _: "unknown", created_at=NOW)

    assert result.status is CognitiveResultStatus.FAILURE
    assert result.error_type == "ValueError"
    assert "plan options" in (result.error_message or "")
    assert result.goal_id == goal.goal_id


def test_run_contract_rejects_context_for_different_goal() -> None:
    cognition = CognitionCore()
    goal = cognition.create_goal("prepare release", created_at=NOW)
    other = cognition.create_goal("different goal", created_at=NOW)
    context = CognitiveContext.create(other.goal_id)

    result = cognition.run_contract(goal, context=context, created_at=NOW)

    assert result.status is CognitiveResultStatus.FAILURE
    assert result.error_type == "ValueError"
    assert result.goal_id == goal.goal_id


def test_legacy_run_keeps_existing_three_word_planning_semantics() -> None:
    result = CognitionCore().run("prepare release notes today", policy=lambda options: options[-1])

    assert result["plan"]["steps"] == ["prepare release notes", "today"]
    assert result["decision"] == "today"
