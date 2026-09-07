from __future__ import annotations

from typing import Any

import pytest

from self_healing.core import FailureSnapshot, SelfHealingCore
from services.learning import LearningService


def _snapshot(exc: Exception) -> FailureSnapshot:
    return FailureSnapshot.create(exc, {"operation": "strategy_test"})


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
            details={"strategy": strategy},
        )


def test_learning_strategy_keeps_default_order_without_samples() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    snapshot = _snapshot(ValueError("invalid"))

    assert healer._ordered_strategies(snapshot) == (
        "rebuild_context",
        "retry_safe",
        "fallback_default",
    )


def test_learning_strategy_requires_minimum_samples() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    _record(learning, "retry_safe", True, 2)

    snapshot = _snapshot(ValueError("invalid"))

    assert healer._ordered_strategies(snapshot) == (
        "rebuild_context",
        "retry_safe",
        "fallback_default",
    )


def test_learning_strategy_prefers_high_success_rate() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    _record(learning, "retry_safe", True, 3)
    _record(learning, "rebuild_context", False, 3)

    snapshot = _snapshot(ValueError("invalid"))

    assert healer._ordered_strategies(snapshot)[0] == "retry_safe"
    assert healer._select_strategy(snapshot) == "retry_safe"


def test_learning_strategy_prefers_higher_rate_over_sample_count() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    _record(learning, "retry_safe", True, 3)
    _record(learning, "rebuild_context", True, 4)
    learning.record(
        "self_healing.recovery",
        0.0,
        success=False,
        details={"strategy": "rebuild_context"},
    )

    snapshot = _snapshot(ValueError("invalid"))

    assert healer._select_strategy(snapshot) == "retry_safe"


def test_learning_strategy_uses_sample_count_when_rates_match() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    _record(learning, "retry_safe", True, 4)
    _record(learning, "rebuild_context", True, 3)

    snapshot = _snapshot(ValueError("invalid"))

    assert healer._select_strategy(snapshot) == "retry_safe"


def test_learning_strategy_preserves_candidate_order_when_scores_match() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    _record(learning, "retry_safe", True, 3)
    _record(learning, "rebuild_context", True, 3)

    snapshot = _snapshot(ValueError("invalid"))

    assert healer._select_strategy(snapshot) == "rebuild_context"


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (
            KeyError("missing"),
            ("fallback_default", "retry_safe", "rebuild_context"),
        ),
        (
            ValueError("invalid"),
            ("rebuild_context", "retry_safe", "fallback_default"),
        ),
        (
            TypeError("invalid"),
            ("rebuild_context", "retry_safe", "fallback_default"),
        ),
        (
            RuntimeError("failure"),
            ("rebuild_context", "retry_safe", "fallback_default"),
        ),
    ],
)
def test_strategy_candidates_are_deterministic(
    exception: Exception,
    expected: tuple[str, ...],
) -> None:
    healer = SelfHealingCore()
    snapshot = _snapshot(exception)

    assert healer._strategy_candidates(snapshot) == expected


def test_learning_failure_is_counted_as_negative_experience() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    _record(learning, "retry_safe", False, 3)
    _record(learning, "rebuild_context", True, 3)

    snapshot = _snapshot(ValueError("invalid"))

    assert healer._select_strategy(snapshot) == "rebuild_context"

    records = healer.learning_records()
    assert len(records) == 6
    assert sum(not record.success for record in records) == 3


def test_learning_strategy_ignores_non_self_healing_records() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    for _ in range(10):
        learning.record(
            "planner.recovery",
            1.0,
            success=True,
            details={"strategy": "retry_safe"},
        )

    snapshot = _snapshot(ValueError("invalid"))

    assert healer._select_strategy(snapshot) == "rebuild_context"


def test_learning_strategy_ignores_unknown_strategy_records() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    _record(learning, "unknown_strategy", True, 10)

    snapshot = _snapshot(ValueError("invalid"))

    assert healer._select_strategy(snapshot) == "rebuild_context"


def test_learning_strategy_selection_is_reflected_in_recovery_plan() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    _record(learning, "retry_safe", True, 3)
    _record(learning, "rebuild_context", False, 3)

    snapshot = _snapshot(ValueError("invalid"))
    plan = healer.plan_recovery(snapshot)

    assert plan.strategy == "retry_safe"
    assert plan.trace_id


def test_learning_strategy_does_not_change_when_learning_is_unavailable() -> None:
    healer = SelfHealingCore()

    snapshot = _snapshot(KeyError("missing"))

    assert healer.learned is False
    assert healer._select_strategy(snapshot) == "fallback_default"


def test_learning_summary_exposes_strategy_statistics() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    _record(learning, "retry_safe", True, 3)
    _record(learning, "retry_safe", False, 1)
    _record(learning, "rebuild_context", True, 3)

    summary = healer.learning_summary()

    assert summary["enabled"] is True
    assert summary["record_count"] == 7
    assert summary["successes"] == 6
    assert summary["failures"] == 1
    assert summary["success_rate"] == pytest.approx(6 / 7)

    strategies = summary["strategies"]
    assert strategies["retry_safe"]["count"] == 4
    assert strategies["retry_safe"]["successes"] == 3
    assert strategies["retry_safe"]["failures"] == 1
    assert strategies["retry_safe"]["success_rate"] == pytest.approx(0.75)

    assert strategies["rebuild_context"]["count"] == 3
    assert strategies["rebuild_context"]["successes"] == 3
    assert strategies["rebuild_context"]["failures"] == 0
    assert strategies["rebuild_context"]["success_rate"] == 1.0


def test_learning_strategy_does_not_modify_learning_records() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    _record(learning, "retry_safe", True, 3)

    before = learning.records()
    snapshot = _snapshot(ValueError("invalid"))

    healer._select_strategy(snapshot)

    after = learning.records()

    assert after == before


def test_learning_strategy_selection_is_repeatable() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    _record(learning, "retry_safe", True, 4)
    _record(learning, "rebuild_context", True, 3)

    snapshot = _snapshot(ValueError("invalid"))

    results = tuple(healer._select_strategy(snapshot) for _ in range(10))

    assert results == ("retry_safe",) * 10


def test_recovery_uses_learned_strategy() -> None:
    learning = LearningService()
    learning.start()
    healer = SelfHealingCore(learning_service=learning)

    _record(learning, "retry_safe", True, 3)
    _record(learning, "rebuild_context", False, 3)

    def fail() -> Any:
        raise ValueError("invalid")

    result = healer.execute_safe(fail)

    assert result["strategy"] == "retry_safe"
    assert healer.recovered == 1
    assert healer.failed == 0

    latest = learning.latest("self_healing.recovery")
    assert latest is not None
    assert latest.success is True
    assert latest.details["strategy"] == "retry_safe"
