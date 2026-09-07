from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from foundation.enums import LifecycleState
from services.policy import (
    PolicyDecision,
    PolicyException,
    PolicyRule,
    PolicyService,
)


def test_default_state() -> None:
    service = PolicyService()
    assert service.state == LifecycleState.CREATED
    assert service.count() == 0


def test_register_and_get() -> None:
    service = PolicyService()
    rule = PolicyRule("allow", lambda context: True)
    service.register(rule)
    assert service.get("allow") is rule
    assert service.contains("allow")
    assert service.count() == 1


def test_duplicate_rule_rejected() -> None:
    service = PolicyService()
    service.register(PolicyRule("allow", lambda context: True))
    with pytest.raises(PolicyException):
        service.register(PolicyRule("allow", lambda context: True))


def test_unregister() -> None:
    service = PolicyService()
    service.register(PolicyRule("allow", lambda context: True))
    rule = service.unregister("allow")
    assert rule is not None
    assert not service.contains("allow")
    assert service.unregister("missing") is None


def test_priority_order_is_deterministic() -> None:
    service = PolicyService()
    service.register(PolicyRule("low", lambda context: True, priority=1))
    service.register(PolicyRule("high", lambda context: True, priority=10))
    decision = service.evaluate()
    assert decision.policy == "high"
    assert decision.allowed


def test_policy_denied() -> None:
    service = PolicyService()
    service.register(PolicyRule("deny", lambda context: False))
    decision = service.evaluate()
    assert isinstance(decision, PolicyDecision)
    assert not decision.allowed
    assert decision.policy == ""


def test_default_decision() -> None:
    service = PolicyService(default=True)
    assert service.allow()
    assert service.evaluate().policy == ""


def test_context_is_passed_to_rule() -> None:
    service = PolicyService()
    service.register(
        PolicyRule(
            "admin",
            lambda context: context.get("role") == "admin",
        )
    )
    assert service.allow({"role": "admin"})
    assert not service.allow({"role": "user"})


def test_rule_evaluation_error() -> None:
    def evaluator(context: Mapping[str, Any]) -> bool:
        raise RuntimeError("failure")

    service = PolicyService()
    service.register(PolicyRule("broken", evaluator))
    with pytest.raises(PolicyException):
        service.evaluate()


def test_snapshot() -> None:
    service = PolicyService()
    service.register(PolicyRule("admin", lambda context: True, "Admin access", 5))
    snapshot = service.snapshot()
    assert snapshot["name"] == "policy"
    assert snapshot["default"] is False
    assert snapshot["rule_count"] == 1
    assert snapshot["rules"][0]["name"] == "admin"


def test_lifecycle_and_health() -> None:
    service = PolicyService()
    assert not service.health().healthy
    service.start()
    assert service.health().healthy
    service.suspend()
    assert service.health().degraded
    service.resume()
    assert service.health().healthy
    service.terminate()
    assert service.health().unhealthy
