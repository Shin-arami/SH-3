from __future__ import annotations

from datetime import UTC, datetime

from cognition.contracts import (
    CognitiveContext,
    CognitiveGoal,
    CognitiveLifecycleState,
    CognitiveResultStatus,
)
from cognition.core import CognitionCore
from cognition.decision_boundary import CognitiveDecisionBoundary
from cognition.planner import Planner
from cognition.planning_boundary import CognitivePlanningBoundary

NOW = datetime(2026, 10, 4, 0, 0, tzinfo=UTC)


def _goal() -> CognitiveGoal:
    return CognitiveGoal.create(
        "prepare release today",
        owner="test",
        created_at=NOW,
        correlation_id="corr-10-5",
        trace_id="trace-10-5",
        tenant_id="tenant-10-5",
    )


def _context(goal: CognitiveGoal) -> CognitiveContext:
    return CognitiveContext.create(
        goal.goal_id,
        correlation_id=goal.correlation_id,
        trace_id=goal.trace_id,
        tenant_id=goal.tenant_id,
        values={"suite": "part-10-5"},
    )


def test_run_contract_uses_injected_decision_boundary() -> None:
    boundary = CognitiveDecisionBoundary(lambda options: options[-1])
    cognition = CognitionCore(decision_boundary=boundary)
    goal = _goal()

    result = cognition.run_contract(goal, created_at=NOW)

    assert result.status is CognitiveResultStatus.SUCCESS
    assert result.lifecycle_state is CognitiveLifecycleState.COMPLETED
    decision = result.output["decision"]
    assert decision["selected_option"] == "today"
    assert decision["goal_id"] == goal.goal_id
    assert decision["causation_id"] == result.output["policy"]["evaluation_id"]


def test_run_contract_preserves_context_trace_through_decision_boundary() -> None:
    cognition = CognitionCore(decision_boundary=CognitiveDecisionBoundary(lambda options: options[0]))
    goal = _goal()
    context = _context(goal)

    result = cognition.run_contract(goal, context=context, created_at=NOW)

    assert result.status is CognitiveResultStatus.SUCCESS
    assert result.correlation_id == context.correlation_id
    assert result.trace_id == context.trace_id
    assert result.tenant_id == context.tenant_id
    assert result.metadata["context_id"] == context.context_id
    assert result.output["decision"]["correlation_id"] == context.correlation_id
    assert result.output["decision"]["trace_id"] == context.trace_id
    assert result.output["decision"]["tenant_id"] == context.tenant_id


def test_run_contract_default_decision_matches_existing_decide_semantics() -> None:
    cognition = CognitionCore()
    goal = _goal()
    plan = cognition.plan_contract(goal, created_at=NOW)

    typed_result = cognition.run_contract(goal, created_at=NOW)
    legacy_choice = cognition.decide(list(plan.steps))

    assert typed_result.status is CognitiveResultStatus.SUCCESS
    assert typed_result.output["decision"]["selected_option"] == legacy_choice


def test_run_contract_policy_override_remains_compatible() -> None:
    boundary = CognitiveDecisionBoundary(lambda _: "should-not-be-used")
    cognition = CognitionCore(decision_boundary=boundary)
    goal = CognitiveGoal.create("prepare release", owner="test", created_at=NOW)

    result = cognition.run_contract(goal, policy=lambda options: options[-1], created_at=NOW)

    assert result.status is CognitiveResultStatus.SUCCESS
    assert result.output["decision"]["selected_option"] == "prepare release"


def test_run_contract_invalid_policy_keeps_typed_failure_contract() -> None:
    cognition = CognitionCore(decision_boundary=CognitiveDecisionBoundary())
    goal = _goal()

    result = cognition.run_contract(goal, policy=lambda _: "invalid", created_at=NOW)

    assert result.status is CognitiveResultStatus.FAILURE
    assert result.lifecycle_state is CognitiveLifecycleState.FAILED
    assert result.error_type == "ValueError"
    assert "plan options" in (result.error_message or "")
    assert result.goal_id == goal.goal_id
    assert result.trace_id == goal.trace_id


def test_run_contract_accepts_string_goal_through_typed_path() -> None:
    cognition = CognitionCore(planning_boundary=CognitivePlanningBoundary(Planner(chunk_size=2)))

    result = cognition.run_contract("prepare release today", created_at=NOW)

    assert result.status is CognitiveResultStatus.SUCCESS
    assert result.goal_id == result.output["goal"]["goal_id"]
    assert result.output["plan"]["goal_id"] == result.goal_id
    assert result.output["decision"]["goal_id"] == result.goal_id
    assert result.output["state"]["goal_id"] == result.goal_id
    assert result.causation_id == result.output["decision"]["decision_id"]
