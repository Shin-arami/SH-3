from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from self_healing.core import (
    FailureSnapshot,
    SelfHealingCore,
    SelfHealingException,
)
from services.learning import LearningService


def _snapshot(
    exception: Exception,
    context: dict[str, Any] | None = None,
) -> FailureSnapshot:
    return FailureSnapshot.create(
        exception,
        context or {"operation": "feedback_test"},
    )


def _record(
    learning: LearningService,
    strategy: str,
    success: bool,
    count: int = 1,
) -> None:
    for _ in range(count):
        learning.record(
            "self_healing.recovery",
            1.0 if success else 0.0,
            success=success,
            details={
                "strategy": strategy,
                "operation": "feedback_test",
            },
        )


def test_successful_recovery_creates_learning_feedback() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    snapshot = _snapshot(KeyError("missing"))
    result = healer.recover_with_learning(snapshot)

    assert result["strategy"] == "fallback_default"
    assert healer.recovered == 1
    assert healer.failed == 0

    record = learning.latest("self_healing.recovery")
    assert record is not None
    assert record.success is True
    assert record.value == 1.0
    assert record.details["strategy"] == "fallback_default"
    assert record.details["error_type"] == "KeyError"
    assert record.details["trace_id"] == snapshot.trace_id


def test_failed_recovery_creates_negative_learning_feedback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    def failing_fallback(
        self: SelfHealingCore,
        snapshot: FailureSnapshot,
    ) -> Any:
        raise RuntimeError("recovery failure")

    monkeypatch.setattr(
        SelfHealingCore,
        "_fallback",
        failing_fallback,
    )

    snapshot = _snapshot(KeyError("missing"))

    with pytest.raises(SelfHealingException):
        healer.recover_with_learning(snapshot, max_attempts=1)

    record = learning.latest("self_healing.recovery")
    assert record is not None
    assert record.success is False
    assert record.value == 0.0
    assert record.details["strategy"] == "fallback_default"
    assert record.details["error_type"] == "KeyError"
    assert record.details["recovery_error"] == "recovery failure"


def test_failed_strategy_is_learned_after_repeated_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    def failing_fallback(
        self: SelfHealingCore,
        snapshot: FailureSnapshot,
    ) -> Any:
        raise RuntimeError("fallback unavailable")

    monkeypatch.setattr(
        SelfHealingCore,
        "_fallback",
        failing_fallback,
    )

    for _ in range(3):
        snapshot = _snapshot(KeyError("missing"))
        with pytest.raises(SelfHealingException):
            healer.recover_with_learning(snapshot, max_attempts=1)

    records = learning.records("self_healing.recovery")
    assert len(records) == 3
    assert all(record.success is False for record in records)


def test_learning_feedback_changes_future_strategy_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    def failing_fallback(
        self: SelfHealingCore,
        snapshot: FailureSnapshot,
    ) -> Any:
        raise RuntimeError("fallback unavailable")

    monkeypatch.setattr(
        SelfHealingCore,
        "_fallback",
        failing_fallback,
    )

    for _ in range(3):
        snapshot = _snapshot(KeyError("missing"))
        with pytest.raises(SelfHealingException):
            healer.recover_with_learning(snapshot, max_attempts=1)

    snapshot = _snapshot(KeyError("missing"))

    assert healer._select_strategy(snapshot) == "retry_safe"


def test_learning_feedback_prefers_successful_strategy_after_failure_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    def failing_fallback(
        self: SelfHealingCore,
        snapshot: FailureSnapshot,
    ) -> Any:
        raise RuntimeError("fallback unavailable")

    monkeypatch.setattr(
        SelfHealingCore,
        "_fallback",
        failing_fallback,
    )

    for _ in range(3):
        snapshot = _snapshot(KeyError("missing"))
        with pytest.raises(SelfHealingException):
            healer.recover_with_learning(snapshot, max_attempts=1)

    _record(learning, "retry_safe", True, 3)

    snapshot = _snapshot(KeyError("missing"))

    assert healer._select_strategy(snapshot) == "retry_safe"

    result = healer.recover_with_learning(snapshot, max_attempts=1)

    assert result["strategy"] == "retry_safe"
    assert healer.recovered == 1
    assert healer.failed == 3


def test_feedback_loop_preserves_failure_context() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    context = {
        "operation": "context_feedback",
        "component": "self_healing",
        "request_id": "feedback-001",
    }
    snapshot = _snapshot(ValueError("invalid"), context)

    result = healer.recover_with_learning(snapshot)

    assert result["status"] == "context_rebuilt"

    record = learning.latest("self_healing.recovery")
    assert record is not None
    assert record.success is True
    assert record.details["strategy"] == "rebuild_context"
    assert record.details["operation"] == "context_feedback"
    assert record.details["component"] == "self_healing"
    assert record.details["request_id"] == "feedback-001"


def test_feedback_loop_records_attempt_number() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    snapshot = _snapshot(KeyError("missing"))

    healer.recover_with_learning(snapshot)

    assert healer.attempt_count == 1
    attempt = healer.attempts[0]
    record = learning.latest("self_healing.recovery")

    assert record is not None
    assert record.details["attempt"] == attempt.attempt
    assert attempt.attempt == 1


def test_feedback_loop_records_multiple_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    def failing_fallback(
        self: SelfHealingCore,
        snapshot: FailureSnapshot,
    ) -> Any:
        raise RuntimeError("fallback unavailable")

    monkeypatch.setattr(
        SelfHealingCore,
        "_fallback",
        failing_fallback,
    )

    snapshot = _snapshot(KeyError("missing"))
    result = healer.recover_with_learning(snapshot, max_attempts=3)

    assert result["strategy"] == "retry_safe"
    assert healer.attempt_count == 2

    attempts = healer.attempts
    assert attempts[0].attempt == 1
    assert attempts[0].strategy == "fallback_default"
    assert attempts[0].success is False
    assert attempts[1].attempt == 2
    assert attempts[1].strategy == "retry_safe"
    assert attempts[1].success is True

    records = learning.records("self_healing.recovery")
    assert len(records) == 2
    assert records[0].success is False
    assert records[1].success is True


def test_learning_failure_does_not_break_feedback_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    snapshot = _snapshot(KeyError("missing"))

    result = healer.recover_with_learning(snapshot)

    assert result["strategy"] == "fallback_default"
    assert healer.recovered == 1
    assert healer.failed == 0
    assert healer.attempt_count == 1


def test_feedback_loop_is_disabled_without_learning_service() -> None:
    healer = SelfHealingCore()
    snapshot = _snapshot(KeyError("missing"))

    result = healer.recover_with_learning(snapshot)

    assert result["strategy"] == "fallback_default"
    assert healer.learned is False
    assert healer.recovered == 1
    assert healer.failed == 0


def test_feedback_loop_summary_matches_recorded_feedback() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    snapshot = _snapshot(KeyError("missing"))
    healer.recover_with_learning(snapshot)

    snapshot = _snapshot(ValueError("invalid"))
    healer.recover_with_learning(snapshot)

    summary = healer.learning_summary()

    assert summary["enabled"] is True
    assert summary["record_count"] == 2
    assert summary["successes"] == 2
    assert summary["failures"] == 0
    assert summary["success_rate"] == 1.0

    assert summary["strategies"]["fallback_default"]["count"] == 1
    assert summary["strategies"]["rebuild_context"]["count"] == 1


def test_feedback_loop_does_not_duplicate_learning_records() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    snapshot = _snapshot(KeyError("missing"))

    healer.recover_with_learning(snapshot)

    assert learning.count("self_healing.recovery") == 1
    assert healer.attempt_count == 1


def test_feedback_loop_keeps_attempt_history_consistent() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    snapshot = _snapshot(KeyError("missing"))

    healer.recover_with_learning(snapshot)

    attempts = healer.attempts
    records = learning.records("self_healing.recovery")

    assert len(attempts) == len(records)
    assert attempts[0].strategy == records[0].details["strategy"]
    assert attempts[0].success is records[0].success


def test_feedback_loop_reset_clears_runtime_state_but_not_learning() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    snapshot = _snapshot(KeyError("missing"))
    healer.recover_with_learning(snapshot)

    assert learning.count("self_healing.recovery") == 1

    healer.reset()

    assert healer.detected == 0
    assert healer.recovered == 0
    assert healer.failed == 0
    assert healer.attempt_count == 0
    assert learning.count("self_healing.recovery") == 1


def test_feedback_loop_uses_latest_learning_statistics() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    _record(learning, "fallback_default", False, 3)
    _record(learning, "retry_safe", True, 3)

    snapshot = _snapshot(KeyError("missing"))

    assert healer._select_strategy(snapshot) == "retry_safe"

    _record(learning, "retry_safe", False, 3)
    _record(learning, "fallback_default", True, 3)

    assert healer._select_strategy(snapshot) == "fallback_default"


def test_feedback_loop_keeps_learning_records_immutable() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    snapshot = _snapshot(KeyError("missing"))
    healer.recover_with_learning(snapshot)

    record = learning.latest("self_healing.recovery")
    assert record is not None

    details = record.details

    with pytest.raises(TypeError):
        details["strategy"] = "modified"  # type: ignore[index]

    assert record.details["strategy"] == "fallback_default"
