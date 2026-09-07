from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from self_healing.core import SelfHealingCore, SelfHealingException
from services.learning import LearningService


def test_learning_service_records_successful_recovery() -> None:
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
    assert result["strategy"] == "fallback_default"
    assert healer.detected == 1
    assert healer.recovered == 1
    assert healer.failed == 0

    records = learning.records("self_healing.recovery")

    assert len(records) == 1

    record = records[0]
    assert record.key == "self_healing.recovery"
    assert record.value == 1.0
    assert record.success is True
    assert record.details["strategy"] == "fallback_default"
    assert record.details["error_type"] == "KeyError"
    assert healer.last_failure is not None
    assert record.details["trace_id"] == healer.last_failure.trace_id
    assert record.details["recovery_result"]["status"] == "fallback_used"


def test_learning_service_records_failed_recovery() -> None:
    class FailingHealer(SelfHealingCore):
        def _fallback(self, snapshot: Any) -> Any:
            raise RuntimeError("recovery failure")

    learning = LearningService()
    learning.start()
    healer = FailingHealer(learning_service=learning)

    snapshot = healer.detect(KeyError("missing"), {})

    with pytest.raises(SelfHealingException):
        healer.recover(snapshot)

    records = learning.records("self_healing.recovery")

    assert len(records) == 1

    record = records[0]
    assert record.key == "self_healing.recovery"
    assert record.value == 0.0
    assert record.success is False
    assert record.details["strategy"] == "fallback_default"
    assert record.details["error_type"] == "KeyError"
    assert record.details["recovery_error"] == "recovery failure"
    assert healer.recovered == 0
    assert healer.failed == 1


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
    assert record.details["error_type"] == "ValueError"
    assert healer.last_failure is not None
    assert healer.last_plan is not None
    assert record.details["trace_id"] == healer.last_failure.trace_id
    assert record.details["plan_id"] == healer.last_plan.trace_id
    assert record.details["recovery_result"]["strategy"] == "rebuild_context"


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
    assert healer.failed == 0
    assert learning.count("self_healing.recovery") == 3

    records = learning.records("self_healing.recovery")

    assert len(records) == 3
    assert [record.details["strategy"] for record in records] == [
        "fallback_default",
        "rebuild_context",
        "fallback_default",
    ]
    assert all(record.success for record in records)


def test_learning_summary_contains_recovery_statistics() -> None:
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

    summary = healer.learning_summary()

    assert summary["enabled"] is True
    assert summary["record_count"] == 3
    assert summary["successes"] == 3
    assert summary["failures"] == 0
    assert summary["success_rate"] == 1.0

    strategies = summary["strategies"]

    assert strategies["fallback_default"]["count"] == 2
    assert strategies["fallback_default"]["successes"] == 2
    assert strategies["fallback_default"]["failures"] == 0
    assert strategies["fallback_default"]["success_rate"] == 1.0

    assert strategies["rebuild_context"]["count"] == 1
    assert strategies["rebuild_context"]["successes"] == 1
    assert strategies["rebuild_context"]["failures"] == 0
    assert strategies["rebuild_context"]["success_rate"] == 1.0


def test_learning_records_are_available_from_core() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    def fail() -> None:
        raise KeyError("missing")

    healer.execute_safe(fail)

    records = healer.learning_records()

    assert len(records) == 1
    assert records[0].key == "self_healing.recovery"
    assert records[0].details["strategy"] == "fallback_default"


def test_learning_is_used_after_minimum_samples() -> None:
    learning = LearningService()
    learning.start()

    learning.record(
        "self_healing.recovery",
        1.0,
        success=True,
        details={"strategy": "rebuild_context"},
    )
    learning.record(
        "self_healing.recovery",
        1.0,
        success=True,
        details={"strategy": "rebuild_context"},
    )
    learning.record(
        "self_healing.recovery",
        1.0,
        success=True,
        details={"strategy": "rebuild_context"},
    )
    learning.record(
        "self_healing.recovery",
        0.0,
        success=False,
        details={"strategy": "fallback_default"},
    )
    learning.record(
        "self_healing.recovery",
        0.0,
        success=False,
        details={"strategy": "fallback_default"},
    )
    learning.record(
        "self_healing.recovery",
        0.0,
        success=False,
        details={"strategy": "fallback_default"},
    )

    healer = SelfHealingCore(learning_service=learning)

    snapshot = healer.detect(ValueError("invalid"), {})

    plan = healer.plan_recovery(snapshot)

    assert plan.strategy == "rebuild_context"


def test_learning_service_failure_does_not_break_recovery() -> None:
    class BrokenLearningService(LearningService):
        def record(
            self,
            key: str,
            value: float,
            success: bool = True,
            details: Mapping[str, Any] | None = None,
        ) -> Any:
            raise RuntimeError("learning storage failure")

    learning = BrokenLearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    def fail() -> None:
        raise KeyError("missing")

    result = healer.execute_safe(
        fail,
        context={"operation": "learning_failure"},
    )

    assert result["status"] == "fallback_used"
    assert result["strategy"] == "fallback_default"
    assert healer.detected == 1
    assert healer.recovered == 1
    assert healer.failed == 0
    assert healer.last_result == result


def test_learning_information_is_in_core_snapshot() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    def fail() -> None:
        raise KeyError("missing")

    healer.execute_safe(fail)

    snapshot = healer.snapshot()

    assert snapshot["learning"]["enabled"] is True
    assert snapshot["learning"]["record_count"] == 1
    assert snapshot["learning"]["successes"] == 1
    assert snapshot["learning"]["failures"] == 0
    assert snapshot["learning"]["success_rate"] == 1.0
    assert snapshot["learning"]["strategies"]["fallback_default"]["count"] == 1


def test_learning_service_can_be_disabled_without_breaking_recovery() -> None:
    healer = SelfHealingCore()

    def fail() -> None:
        raise KeyError("missing")

    result = healer.execute_safe(fail)

    assert result["status"] == "fallback_used"
    assert result["strategy"] == "fallback_default"
    assert healer.recovered == 1
    assert healer.learning_records() == ()
    assert healer.learning_summary()["enabled"] is False
