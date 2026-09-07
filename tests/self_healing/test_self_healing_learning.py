from __future__ import annotations

from typing import Any

import pytest

from self_healing.core import SelfHealingCore, SelfHealingException
from services.learning import LearningService


def test_self_healing_learning_service_records_recovery() -> None:
    learning = LearningService()
    learning.start()

    healer = SelfHealingCore(learning_service=learning)

    def fail() -> None:
        raise KeyError("missing")

    result = healer.execute_safe(
        fail,
        context={"operation": "integration_test"},
    )

    assert result["status"] == "fallback_used"
    assert healer.detected == 1
    assert healer.recovered == 1
    assert learning.count() == 1

    records = learning.records()
    assert len(records) == 1

    record = records[0]
    assert record.success is True
    assert record.key == "self_healing.recovery"
    assert record.details["strategy"] == "fallback_default"


def test_self_healing_learning_records_failed_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    learning = LearningService()
    learning.start()

    healer = SelfHealingCore(learning_service=learning)

    def failing_recovery(self: SelfHealingCore, snapshot: Any) -> Any:
        raise RuntimeError("recovery failure")

    monkeypatch.setattr(
        SelfHealingCore,
        "_fallback",
        failing_recovery,
    )

    with pytest.raises(SelfHealingException):
        healer.execute_safe(
            lambda: (_ for _ in ()).throw(KeyError("missing")),
        )

    assert healer.detected == 1
    assert healer.recovered == 0
    assert healer.failed == 1

    record = learning.latest("self_healing.recovery")

    assert record is not None
    assert record.success is False
    assert record.value == 0.0
    assert record.details["strategy"] == "fallback_default"
    assert record.details["error_type"] == "KeyError"
    assert record.details["recovery_error"] == "recovery failure"


def test_learning_records_strategy_information() -> None:
    learning = LearningService()
    learning.start()

    healer = SelfHealingCore(learning_service=learning)

    def fail() -> None:
        raise ValueError("invalid")

    result = healer.execute_safe(
        fail,
        context={
            "operation": "strategy_test",
            "component": "self_healing",
        },
    )

    assert result["strategy"] == "rebuild_context"

    record = learning.latest("self_healing.recovery")

    assert record is not None
    assert record.success is True
    assert record.details["strategy"] == "rebuild_context"
    assert record.details["operation"] == "strategy_test"
    assert record.details["component"] == "self_healing"


def test_multiple_recoveries_are_recorded() -> None:
    learning = LearningService()
    learning.start()

    healer = SelfHealingCore(learning_service=learning)

    def fail_key() -> None:
        raise KeyError("missing")

    def fail_value() -> None:
        raise ValueError("invalid")

    healer.execute_safe(fail_key)
    healer.execute_safe(fail_value)
    healer.execute_safe(fail_key)

    assert healer.detected == 3
    assert healer.recovered == 3
    assert learning.count("self_healing.recovery") == 3
    assert learning.success_rate("self_healing.recovery") == 1.0
