from __future__ import annotations

import pytest

from foundation.enums import LifecycleState, Severity
from services.healing import (
    HealingAction,
    HealingException,
    HealingResult,
    HealingService,
)


def test_default_state() -> None:
    service = HealingService()
    assert service.state == LifecycleState.CREATED
    assert service.actions == ()
    assert service.failures == ()
    assert service.history == ()
    assert service.last_result is None


def test_register_action() -> None:
    service = HealingService()
    action = HealingAction("restart", lambda context: context["service"])
    service.register_action(action)
    assert service.has_action("restart")
    assert service.get_action("restart") is action
    assert service.actions == ("restart",)


def test_unregister_action() -> None:
    service = HealingService()
    service.register_action(HealingAction("restart", lambda _: True))
    removed = service.unregister_action("restart")
    assert removed is not None
    assert removed.name == "restart"
    assert not service.has_action("restart")
    assert service.unregister_action("restart") is None


def test_register_failure() -> None:
    service = HealingService()
    service.register_failure(
        "planner_failure",
        {"service": "planner", "attempt": 1},
    )
    assert service.has_failure("planner_failure")
    assert service.failures == ("planner_failure",)


def test_heal_success() -> None:
    service = HealingService()
    service.register_action(
        HealingAction(
            "restart",
            lambda context: context["service"],
        )
    )
    service.register_failure(
        "planner_failure",
        {"service": "planner"},
    )

    result = service.heal("planner_failure", "restart")

    assert isinstance(result, HealingResult)
    assert result.failure == "planner_failure"
    assert result.action == "restart"
    assert result.success is True
    assert result.result == "planner"
    assert result.error is None
    assert not service.has_failure("planner_failure")
    assert service.last_result is result
    assert service.successful_healings == 1
    assert service.failed_healings == 0


def test_heal_failure_is_recorded() -> None:
    service = HealingService()

    def failing(_: object) -> None:
        raise RuntimeError("restart failed")

    service.register_action(HealingAction("restart", failing))
    service.register_failure("planner_failure")

    result = service.heal("planner_failure", "restart")

    assert result.success is False
    assert result.error == "restart failed"
    assert service.has_failure("planner_failure")
    assert service.successful_healings == 0
    assert service.failed_healings == 1


def test_unknown_action_is_rejected() -> None:
    service = HealingService()
    with pytest.raises(HealingException):
        service.heal("planner_failure", "restart")


def test_action_and_result_are_immutable() -> None:
    action = HealingAction("restart", lambda _: True)
    result = HealingResult("failure", "restart", True)

    with pytest.raises(AttributeError):
        action.name = "other"  # type: ignore[misc]

    with pytest.raises(AttributeError):
        result.success = False  # type: ignore[misc]


def test_snapshot() -> None:
    service = HealingService()
    service.register_action(HealingAction("restart", lambda _: "ok"))
    service.register_failure("planner_failure")
    service.heal("planner_failure", "restart")

    snapshot = service.snapshot()

    assert snapshot["name"] == "healing"
    assert snapshot["state"] == LifecycleState.CREATED.value
    assert snapshot["started"] is False
    assert snapshot["actions"] == ("restart",)
    assert snapshot["failures"] == ()
    assert len(snapshot["history"]) == 1
    assert snapshot["last_result"]["success"] is True


def test_health_lifecycle() -> None:
    service = HealingService()

    health = service.health()
    assert health.healthy is False
    assert health.severity == Severity.LOW

    service.start()

    health = service.health()
    assert health.healthy is True
    assert health.severity == Severity.INFO

    service.register_failure("planner_failure")

    health = service.health()
    assert health.healthy is False
    assert health.degraded is True
    assert health.severity == Severity.MEDIUM

    service.suspend()

    health = service.health()
    assert health.healthy is False
    assert health.severity == Severity.MEDIUM

    service.resume()
    service.terminate()

    health = service.health()
    assert health.healthy is False
    assert health.unhealthy is True
    assert health.severity == Severity.HIGH
