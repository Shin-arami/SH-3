from __future__ import annotations

from typing import Any, cast

import pytest

from services.planner import (
    Plan,
    PlannerException,
    PlannerService,
    PlanStep,
)


def test_planner_defaults() -> None:
    planner = PlannerService()
    assert planner.name == "planner"
    assert planner.plan_count() == 0
    assert planner.plans() == ()


def test_plan_step_is_immutable() -> None:
    step = PlanStep("load", "load_data", {"source": "memory"})
    with pytest.raises((AttributeError, TypeError)):
        step.name = "other"  # type: ignore[misc]
    with pytest.raises(TypeError):
        cast(Any, step.parameters)["x"] = 1


def test_plan_is_immutable() -> None:
    plan = Plan("startup", "initialize runtime")
    with pytest.raises((AttributeError, TypeError)):
        plan.name = "other"  # type: ignore[misc]
    with pytest.raises(TypeError):
        cast(Any, plan.metadata)["x"] = 1


def test_create_plan_requires_active_service() -> None:
    planner = PlannerService()
    with pytest.raises(PlannerException):
        planner.create_plan("startup", "initialize runtime")


def test_create_and_get_plan() -> None:
    planner = PlannerService()
    planner.start()

    step = PlanStep("load", "load_data", {"source": "memory"})
    plan = planner.create_plan(
        "startup",
        "initialize runtime",
        (step,),
        {"version": "1"},
    )

    assert planner.get_plan("startup") is plan
    assert plan.steps == (step,)
    assert plan.metadata["version"] == "1"
    assert planner.plan_count() == 1


def test_duplicate_plan_is_rejected() -> None:
    planner = PlannerService()
    planner.start()
    planner.create_plan("startup", "initialize runtime")

    with pytest.raises(PlannerException):
        planner.create_plan("startup", "other goal")


def test_remove_plan() -> None:
    planner = PlannerService()
    planner.start()
    plan = planner.create_plan("startup", "initialize runtime")

    assert planner.remove_plan("startup") is plan
    assert planner.get_plan("startup") is None
    assert planner.plan_count() == 0


def test_clear_plans() -> None:
    planner = PlannerService()
    planner.start()
    planner.create_plan("a", "goal a")
    planner.create_plan("b", "goal b")

    planner.clear()

    assert planner.plan_count() == 0
    assert planner.plans() == ()


def test_snapshot() -> None:
    planner = PlannerService()
    planner.start()
    planner.create_plan("startup", "initialize runtime")

    snapshot = planner.snapshot()

    assert snapshot["name"] == "planner"
    assert snapshot["state"] == "ACTIVE"
    assert snapshot["plan_count"] == 1
    assert snapshot["plans"][0]["name"] == "startup"


def test_terminate_clears_plans() -> None:
    planner = PlannerService()
    planner.start()
    planner.create_plan("startup", "initialize runtime")

    planner.terminate()

    assert planner.plan_count() == 0
