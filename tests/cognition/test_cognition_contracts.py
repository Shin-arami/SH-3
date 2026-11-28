from __future__ import annotations

from collections.abc import MutableMapping
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, cast

import pytest

from cognition.contracts import (
    COGNITION_CONTRACT_VERSION,
    CognitiveContext,
    CognitiveDecision,
    CognitiveGoal,
    CognitiveLifecycleState,
    CognitivePlan,
    CognitiveResult,
    CognitiveResultStatus,
    CognitiveState,
)

NOW = datetime(2026, 10, 4, 0, 0, tzinfo=UTC)


def _goal() -> CognitiveGoal:
    return CognitiveGoal.create(
        "prepare release",
        owner="test",
        created_at=NOW,
        success_criteria=("notes ready",),
        constraints={"window": "test"},
        correlation_id="corr-1",
        trace_id="trace-1",
        tenant_id="tenant-1",
    )


def test_goal_contract_is_immutable_and_traceable() -> None:
    goal = _goal()

    assert goal.goal_id == CognitiveGoal.create(
        "prepare release",
        owner="test",
        created_at=NOW,
        success_criteria=("notes ready",),
        constraints={"window": "test"},
    ).goal_id
    assert goal.version == COGNITION_CONTRACT_VERSION
    assert goal.lifecycle_state is CognitiveLifecycleState.CREATED
    assert isinstance(goal.constraints, MappingProxyType)
    assert goal.to_dict()["created_at"] == NOW.isoformat()
    assert goal.trace_id == "trace-1"
    with pytest.raises(AttributeError):
        cast(Any, goal).intent = "changed"
    with pytest.raises(TypeError):
        cast(MutableMapping[str, Any], goal.constraints)["new"] = "value"


def test_context_and_state_preserve_goal_trace_contract() -> None:
    goal = _goal()
    context = CognitiveContext.create(
        goal.goal_id,
        correlation_id=goal.correlation_id,
        trace_id=goal.trace_id,
        tenant_id=goal.tenant_id,
        values={"source": "test"},
    )
    state = CognitiveState.from_goal(
        goal,
        context=context,
        steps=("plan", "validate"),
        assumptions=("input trusted",),
        results={"count": 2},
        updated_at=NOW,
    )

    assert context.goal_id == goal.goal_id
    assert context.trace_id == goal.trace_id
    assert state.goal_id == goal.goal_id
    assert state.correlation_id == goal.correlation_id
    assert state.trace_id == goal.trace_id
    assert state.context is context
    assert state.steps == ("plan", "validate")
    assert state.results["count"] == 2
    assert state.to_dict()["context"]["context_id"] == context.context_id


def test_plan_and_decision_contracts_validate_dependencies_and_selection() -> None:
    goal = _goal()
    plan = CognitivePlan.create(
        goal,
        ("prepare", "review"),
        dependencies=(("review", "prepare"),),
        created_at=NOW,
    )
    decision = CognitiveDecision.create(
        goal,
        plan.steps,
        selected_option="review",
        rationale="highest deterministic utility",
        utility=0.8,
        risk=0.2,
        created_at=NOW,
    )

    assert plan.goal_id == goal.goal_id
    assert plan.dependencies == (("review", "prepare"),)
    assert decision.selected_option == "review"
    assert decision.options == plan.steps
    assert decision.trace_id == goal.trace_id

    with pytest.raises(ValueError, match="selected_option"):
        CognitiveDecision.create(goal, plan.steps, selected_option="missing", created_at=NOW)
    with pytest.raises(ValueError, match="dependencies"):
        CognitivePlan.create(goal, ("prepare", "review"), dependencies=(("missing", "review"),), created_at=NOW)
    with pytest.raises(ValueError, match="options"):
        CognitiveDecision.create(goal, ("prepare", "prepare"), created_at=NOW)


def test_result_contract_validates_status_and_error_context() -> None:
    goal = _goal()
    result = CognitiveResult.create(
        goal,
        status=CognitiveResultStatus.FAILURE,
        error_type="ValueError",
        error_message="invalid input",
        created_at=NOW,
    )

    assert result.status is CognitiveResultStatus.FAILURE
    assert result.lifecycle_state is CognitiveLifecycleState.COMPLETED
    assert result.error_type == "ValueError"
    assert result.error_message == "invalid input"
    assert result.trace_id == goal.trace_id
    assert result.to_dict()["status"] == "failure"


def test_contract_creation_is_deterministic_for_same_content() -> None:
    first = CognitiveGoal.create("deterministic goal", owner="test", created_at=NOW)
    second = CognitiveGoal.create("deterministic goal", owner="test", created_at=NOW)

    assert first == second
    assert first.goal_id == second.goal_id
    assert CognitiveGoal.create("deterministic goal", owner="different", created_at=NOW).goal_id != first.goal_id


def test_existing_cognition_api_remains_unchanged() -> None:
    from cognition.core import CognitionCore

    result = CognitionCore().run(
        "prepare release notes today",
        policy=lambda options: options[-1],
    )

    assert result["decision"] == "today"
    assert result["plan"]["steps"] == ["prepare release notes", "today"]
