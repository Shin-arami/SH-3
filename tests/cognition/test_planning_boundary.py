from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest

from cognition.contracts import CognitiveContext, CognitiveGoal
from cognition.planner import Planner
from cognition.planning_boundary import CognitivePlanningBoundary

NOW = datetime(2026, 10, 4, 0, 0, tzinfo=UTC)


class StubBackend:
    def build_plan(self, goal: str) -> dict[str, object]:
        return {
            "goal": goal,
            "tree": {
                "name": goal,
                "children": [{"name": "inspect"}, {"name": "apply"}],
            },
            "created_at": NOW.isoformat(),
            "trace_id": "backend-trace",
        }


def test_boundary_converts_goal_to_typed_plan_without_changing_legacy_planner() -> None:
    goal = CognitiveGoal.create(
        "prepare release notes today",
        owner="test",
        created_at=NOW,
        correlation_id="corr-1",
        trace_id="trace-1",
        tenant_id="tenant-1",
    )
    boundary = CognitivePlanningBoundary(Planner(chunk_size=3))

    result = boundary.build_plan(goal, created_at=NOW)
    legacy = Planner(chunk_size=3).build_plan(goal.intent)

    assert result.goal_id == goal.goal_id
    assert result.steps == tuple(item["name"] for item in legacy["tree"]["children"])
    assert result.correlation_id == goal.correlation_id
    assert result.trace_id == goal.trace_id
    assert result.tenant_id == goal.tenant_id
    assert result.metadata["legacy_plan_trace_id"] == legacy["trace_id"]


def test_boundary_supports_replaceable_planning_backend() -> None:
    goal = CognitiveGoal.create("prepare release", owner="test", created_at=NOW)

    result = CognitivePlanningBoundary(StubBackend()).build_plan(goal, created_at=NOW)

    assert result.steps == ("inspect", "apply")
    assert result.metadata["legacy_plan_trace_id"] == "backend-trace"


def test_boundary_builds_goal_for_legacy_string_input() -> None:
    result = CognitivePlanningBoundary(Planner(chunk_size=2)).build_plan("one two three four", created_at=NOW)

    assert result.steps == ("one two", "three four")
    assert result.goal_id.startswith("goal:")
    assert result.plan_id.startswith("plan:")


def test_boundary_preserves_context_trace_fields() -> None:
    goal = CognitiveGoal.create(
        "prepare release",
        created_at=NOW,
        correlation_id="corr-1",
        trace_id="trace-1",
        tenant_id="tenant-1",
    )
    context = CognitiveContext.create(
        goal.goal_id,
        correlation_id="corr-2",
        causation_id="cause-1",
        trace_id="trace-2",
        tenant_id="tenant-2",
    )

    result = CognitivePlanningBoundary().build_plan(goal, context=context, created_at=NOW)

    assert result.correlation_id == context.correlation_id
    assert result.causation_id == context.causation_id
    assert result.trace_id == context.trace_id
    assert result.tenant_id == context.tenant_id
    assert result.metadata["planning_context_id"] == context.context_id


def test_boundary_rejects_mismatched_context() -> None:
    goal = CognitiveGoal.create("prepare release", created_at=NOW)
    other = CognitiveGoal.create("different goal", created_at=NOW)
    context = CognitiveContext.create(other.goal_id)

    with pytest.raises(ValueError, match="goal_id"):
        CognitivePlanningBoundary().build_plan(goal, context=context, created_at=NOW)


def test_boundary_rejects_invalid_backend_result() -> None:
    class InvalidBackend:
        def build_plan(self, goal: str) -> dict[str, object]:
            return {"goal": goal}

    goal = CognitiveGoal.create("prepare release", created_at=NOW)

    with pytest.raises(ValueError, match="tree"):
        CognitivePlanningBoundary(InvalidBackend()).build_plan(goal, created_at=NOW)


def test_boundary_plan_identity_is_deterministic() -> None:
    first_goal = CognitiveGoal.create("prepare release", owner="test", created_at=NOW)
    second_goal = CognitiveGoal.create("prepare release", owner="test", created_at=NOW)
    boundary = CognitivePlanningBoundary(Planner(chunk_size=2))

    first = boundary.build_plan(first_goal, created_at=NOW)
    second = boundary.plan(second_goal, created_at=NOW)

    assert first == second
    assert first.plan_id == second.plan_id


def test_boundary_is_safe_for_concurrent_planning() -> None:
    goal = CognitiveGoal.create("prepare release notes", owner="test", created_at=NOW)
    boundary = CognitivePlanningBoundary(Planner(chunk_size=2))

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: boundary.build_plan(goal, created_at=NOW), range(16)))

    assert all(result == results[0] for result in results)
