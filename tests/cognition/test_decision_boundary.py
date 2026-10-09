from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cognition.contracts import CognitiveContext, CognitiveGoal, CognitivePlan
from cognition.decision_boundary import CognitiveDecisionBoundary
from cognition.policy_boundary import CognitivePolicyBoundary, CognitivePolicyEvaluation

NOW = datetime(2026, 10, 4, 0, 0, tzinfo=UTC)


def _goal() -> CognitiveGoal:
    return CognitiveGoal.create(
        "prepare release",
        owner="test",
        created_at=NOW,
        correlation_id="corr-1",
        trace_id="trace-1",
        tenant_id="tenant-1",
    )


def _plan(goal: CognitiveGoal) -> CognitivePlan:
    return CognitivePlan.create(goal, ("prepare", "review"), created_at=NOW)


def test_decision_boundary_creates_typed_decision_from_plan() -> None:
    goal = _goal()
    plan = _plan(goal)
    decision = CognitiveDecisionBoundary().decide(goal, plan)

    assert decision.goal_id == goal.goal_id
    assert decision.options == plan.steps
    assert decision.selected_option == "prepare"
    assert decision.causation_id == plan.plan_id
    assert decision.correlation_id == goal.correlation_id
    assert decision.trace_id == goal.trace_id
    assert decision.tenant_id == goal.tenant_id


def test_decision_boundary_is_deterministic_for_identical_inputs() -> None:
    goal = _goal()
    plan = _plan(goal)
    boundary = CognitiveDecisionBoundary()

    first = boundary.decide(goal, plan, created_at=NOW)
    second = boundary.decide(goal, plan, created_at=NOW)

    assert first == second
    assert first.decision_id == second.decision_id


def test_decision_boundary_accepts_replaceable_backend() -> None:
    goal = _goal()
    plan = _plan(goal)
    boundary = CognitiveDecisionBoundary(lambda options: options[-1])

    decision = boundary.decide(goal, plan, created_at=NOW)

    assert decision.selected_option == "review"


def test_decision_boundary_preserves_context_trace_and_metadata() -> None:
    goal = _goal()
    plan = _plan(goal)
    context = CognitiveContext.create(
        goal.goal_id,
        correlation_id="corr-context",
        causation_id="cause-context",
        trace_id="trace-context",
        tenant_id="tenant-context",
        metadata={"source": "test"},
    )

    decision = CognitiveDecisionBoundary().decide(goal, plan, context=context, created_at=NOW)

    assert decision.correlation_id == context.correlation_id
    assert decision.trace_id == context.trace_id
    assert decision.tenant_id == context.tenant_id
    assert decision.causation_id == plan.plan_id
    assert decision.metadata["source"] == "test"
    assert decision.metadata["plan_id"] == plan.plan_id


def test_decision_boundary_rejects_plan_for_different_goal() -> None:
    first = _goal()
    second = CognitiveGoal.create("other goal", owner="test", created_at=NOW)
    plan = _plan(second)

    with pytest.raises(ValueError, match="plan goal_id"):
        CognitiveDecisionBoundary().decide(first, plan)


def test_decision_boundary_rejects_context_for_different_goal() -> None:
    goal = _goal()
    other = CognitiveGoal.create("other goal", owner="test", created_at=NOW)
    context = CognitiveContext.create(other.goal_id)

    with pytest.raises(ValueError, match="context goal_id"):
        CognitiveDecisionBoundary().decide(goal, _plan(goal), context=context)


def test_decision_boundary_rejects_invalid_backend_result() -> None:
    goal = _goal()
    plan = _plan(goal)

    with pytest.raises(ValueError, match="one of plan options"):
        CognitiveDecisionBoundary(lambda _: "unknown").decide(goal, plan)


def test_decision_boundary_supports_unresolved_decision() -> None:
    goal = _goal()
    plan = _plan(goal)

    decision = CognitiveDecisionBoundary(lambda _: None).decide(goal, plan, created_at=NOW)

    assert decision.selected_option is None


def test_decision_boundary_rejects_invalid_inputs() -> None:
    goal = _goal()
    plan = _plan(goal)
    boundary = CognitiveDecisionBoundary()

    with pytest.raises(TypeError, match="goal must be CognitiveGoal"):
        boundary.decide("invalid", plan)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="plan must be CognitivePlan"):
        boundary.decide(goal, "invalid")  # type: ignore[arg-type]

def test_decision_boundary_integrates_policy_evaluation_into_context_lifecycle_and_trace() -> None:
    goal = _goal()
    plan = _plan(goal)
    context = CognitiveContext.create(
        goal.goal_id,
        correlation_id="corr-policy",
        trace_id="trace-policy",
        tenant_id="tenant-policy",
        metadata={"source": "policy"},
    )
    evaluation = CognitivePolicyBoundary().evaluate(goal, plan, context=context, created_at=NOW)

    decision = CognitiveDecisionBoundary().decide(
        goal,
        plan,
        context=context,
        policy_evaluation=evaluation,
        created_at=NOW,
    )

    assert decision.lifecycle_state.value == "completed"
    assert decision.causation_id == evaluation.evaluation_id
    assert decision.correlation_id == evaluation.correlation_id
    assert decision.trace_id == evaluation.trace_id
    assert decision.tenant_id == evaluation.tenant_id
    assert decision.metadata["context_id"] == context.context_id
    assert decision.metadata["policy_evaluation_id"] == evaluation.evaluation_id
    assert decision.metadata["policy_id"] == evaluation.policy_id
    assert decision.metadata["policy_version"] == evaluation.policy_version


def test_decision_boundary_requires_allowed_policy_evaluation() -> None:
    goal = _goal()
    plan = _plan(goal)
    evaluation = CognitivePolicyEvaluation.create(
        goal,
        plan,
        allowed=False,
        reason="blocked",
        created_at=NOW,
    )

    with pytest.raises(ValueError, match="must allow decision"):
        CognitiveDecisionBoundary().decide(
            goal,
            plan,
            context=CognitiveContext.create(goal.goal_id, correlation_id=goal.correlation_id),
            policy_evaluation=evaluation,
            created_at=NOW,
        )


def test_decision_boundary_requires_context_for_policy_evaluation() -> None:
    goal = _goal()
    plan = _plan(goal)
    evaluation = CognitivePolicyBoundary().evaluate(goal, plan, created_at=NOW)

    with pytest.raises(ValueError, match="context is required"):
        CognitiveDecisionBoundary().decide(goal, plan, policy_evaluation=evaluation, created_at=NOW)


def test_decision_boundary_rejects_mismatched_policy_trace() -> None:
    goal = _goal()
    plan = _plan(goal)
    context = CognitiveContext.create(goal.goal_id, correlation_id="corr-x", trace_id="trace-x")
    evaluation = CognitivePolicyEvaluation.create(
        goal,
        plan,
        allowed=True,
        reason="accepted",
        context=CognitiveContext.create(goal.goal_id, correlation_id="corr-x", trace_id="trace-y"),
        created_at=NOW,
    )

    with pytest.raises(ValueError, match="trace_id"):
        CognitiveDecisionBoundary().decide(
            goal,
            plan,
            context=context,
            policy_evaluation=evaluation,
            created_at=NOW,
        )


def test_decision_boundary_rejects_policy_evaluation_for_different_goal() -> None:
    goal = _goal()
    other = CognitiveGoal.create("other", owner="test", created_at=NOW)
    plan = _plan(goal)
    evaluation = CognitivePolicyEvaluation.create(other, _plan(other), allowed=True, reason="accepted", created_at=NOW)
    context = CognitiveContext.create(goal.goal_id, correlation_id=goal.correlation_id)

    with pytest.raises(ValueError, match="policy evaluation goal_id"):
        CognitiveDecisionBoundary().decide(
            goal,
            plan,
            context=context,
            policy_evaluation=evaluation,
            created_at=NOW,
        )


def test_decision_boundary_rejects_policy_evaluation_for_different_plan() -> None:
    goal = _goal()
    plan = _plan(goal)
    other_plan = CognitivePlan.create(goal, ("different",), created_at=NOW)
    evaluation = CognitivePolicyEvaluation.create(goal, other_plan, allowed=True, reason="accepted", created_at=NOW)
    context = CognitiveContext.create(goal.goal_id, correlation_id=goal.correlation_id)

    with pytest.raises(ValueError, match="policy evaluation plan_id"):
        CognitiveDecisionBoundary().decide(
            goal,
            plan,
            context=context,
            policy_evaluation=evaluation,
            created_at=NOW,
        )


def test_decision_boundary_rejects_invalid_policy_evaluation_type() -> None:
    goal = _goal()
    plan = _plan(goal)
    context = CognitiveContext.create(goal.goal_id, correlation_id=goal.correlation_id)

    with pytest.raises(TypeError, match="policy_evaluation must be CognitivePolicyEvaluation"):
        CognitiveDecisionBoundary().decide(
            goal,
            plan,
            context=context,
            policy_evaluation=object(),  # type: ignore[arg-type]
            created_at=NOW,
        )


def test_unresolved_policy_integrated_decision_remains_active() -> None:
    goal = _goal()
    plan = _plan(goal)
    context = CognitiveContext.create(goal.goal_id, correlation_id=goal.correlation_id, trace_id=goal.trace_id, tenant_id=goal.tenant_id)
    evaluation = CognitivePolicyBoundary().evaluate(goal, plan, context=context, created_at=NOW)
    decision = CognitiveDecisionBoundary(lambda _: None).decide(
        goal,
        plan,
        context=context,
        policy_evaluation=evaluation,
        created_at=NOW,
    )

    assert decision.selected_option is None
    assert decision.lifecycle_state.value == "active"
    assert decision.causation_id == evaluation.evaluation_id
