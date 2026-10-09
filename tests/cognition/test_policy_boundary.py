from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest

from cognition.contracts import CognitiveContext, CognitiveGoal, CognitivePlan
from cognition.policy_boundary import CognitivePolicyBoundary, CognitivePolicyEvaluation

NOW = datetime(2026, 10, 5, 0, 0, tzinfo=UTC)


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


def test_policy_boundary_creates_deterministic_typed_evaluation() -> None:
    goal = _goal()
    plan = _plan(goal)
    boundary = CognitivePolicyBoundary()

    first = boundary.evaluate(goal, plan, created_at=NOW)
    second = boundary.evaluate(goal, plan, created_at=NOW)

    assert isinstance(first, CognitivePolicyEvaluation)
    assert first == second
    assert first.evaluation_id == second.evaluation_id
    assert first.allowed
    assert first.plan_id == plan.plan_id
    assert first.causation_id == plan.plan_id


def test_policy_boundary_preserves_context_trace_and_metadata() -> None:
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

    evaluation = CognitivePolicyBoundary().evaluate(goal, plan, context=context, created_at=NOW)

    assert evaluation.correlation_id == context.correlation_id
    assert evaluation.trace_id == context.trace_id
    assert evaluation.tenant_id == context.tenant_id
    assert evaluation.metadata["source"] == "test"
    assert evaluation.metadata["context_id"] == context.context_id


def test_policy_boundary_accepts_replaceable_backend() -> None:
    def backend(goal: CognitiveGoal, plan: CognitivePlan, context: CognitiveContext) -> CognitivePolicyEvaluation:
        return CognitivePolicyEvaluation.create(
            goal,
            plan,
            allowed=False,
            policy_id="release-lock",
            reason="release is locked",
            context=context,
            created_at=NOW,
        )

    goal = _goal()
    evaluation = CognitivePolicyBoundary(backend).evaluate(goal, _plan(goal), created_at=NOW)
    assert not evaluation.allowed
    assert evaluation.policy_id == "release-lock"
    assert evaluation.reason == "release is locked"


def test_policy_boundary_rejects_different_goal_plan() -> None:
    first = _goal()
    second = CognitiveGoal.create("other", owner="test", created_at=NOW)

    with pytest.raises(ValueError, match="plan goal_id"):
        CognitivePolicyBoundary().evaluate(first, _plan(second))


def test_policy_boundary_rejects_different_goal_context() -> None:
    goal = _goal()
    other = CognitiveGoal.create("other", owner="test", created_at=NOW)
    context = CognitiveContext.create(other.goal_id)

    with pytest.raises(ValueError, match="context goal_id"):
        CognitivePolicyBoundary().evaluate(goal, _plan(goal), context=context)


def test_policy_boundary_rejects_invalid_backend_result() -> None:
    def backend(goal: CognitiveGoal, plan: CognitivePlan, context: CognitiveContext) -> CognitivePolicyEvaluation:
        return cast(CognitivePolicyEvaluation, object())

    goal = _goal()
    with pytest.raises(TypeError, match="CognitivePolicyEvaluation"):
        CognitivePolicyBoundary(backend).evaluate(goal, _plan(goal))


def test_policy_evaluation_is_immutable() -> None:
    evaluation = CognitivePolicyBoundary().evaluate(_goal(), _plan(_goal()), created_at=NOW)

    with pytest.raises((AttributeError, TypeError)):
        cast(Any, evaluation).allowed = False


def test_policy_evaluation_rejects_invalid_version_and_timestamp() -> None:
    goal = _goal()
    plan = _plan(goal)

    with pytest.raises(ValueError, match="semantic version"):
        CognitivePolicyEvaluation(
            evaluation_id="evaluation",
            goal_id=goal.goal_id,
            plan_id=plan.plan_id,
            policy_id="policy",
            policy_version="1",
            allowed=True,
            reason="ok",
            created_at=NOW,
            correlation_id=goal.correlation_id,
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        CognitivePolicyEvaluation(
            evaluation_id="evaluation",
            goal_id=goal.goal_id,
            plan_id=plan.plan_id,
            policy_id="policy",
            policy_version="1.0.0",
            allowed=True,
            reason="ok",
            created_at=datetime(2026, 10, 5),
            correlation_id=goal.correlation_id,
        )
