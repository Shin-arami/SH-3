from __future__ import annotations

import pytest

from foundation.enums import LifecycleState, Severity
from services.optimizer import (
    OptimizationResult,
    OptimizerException,
    OptimizerService,
)


def test_default_state() -> None:
    service = OptimizerService()
    assert service.state == LifecycleState.CREATED
    assert service.runs == 0
    assert service.last_result is None


def test_optimize_selects_highest_score() -> None:
    service = OptimizerService()
    result = service.optimize(
        ["a", "b", "c"],
        lambda value: {"a": 1.0, "b": 3.0, "c": 2.0}[value],
    )
    assert result.selected == "b"
    assert result.score == 3.0
    assert result.candidates == 3
    assert result.index == 1


def test_optimize_is_deterministic_on_tie() -> None:
    service = OptimizerService()
    result = service.optimize(
        ["first", "second"],
        lambda _: 1.0,
    )
    assert result.selected == "first"
    assert result.index == 0


def test_select_returns_best_candidate() -> None:
    service = OptimizerService()
    assert (
        service.select(
            [1, 2, 3],
            lambda value: float(value),
        )
        == 3
    )


def test_empty_candidates_are_rejected() -> None:
    service = OptimizerService()
    with pytest.raises(ValueError):
        service.optimize([], lambda _: 1.0)


def test_invalid_scorer_is_rejected() -> None:
    service = OptimizerService()
    with pytest.raises(TypeError):
        service.optimize([1], None)  # type: ignore[arg-type]


def test_scorer_failure_is_wrapped() -> None:
    service = OptimizerService()

    def scorer(_: int) -> float:
        raise RuntimeError("failure")

    with pytest.raises(OptimizerException):
        service.optimize([1], scorer)


def test_result_is_immutable() -> None:
    result = OptimizationResult("a", 1.0, 1, 0)
    with pytest.raises(AttributeError):
        result.score = 2.0  # type: ignore[misc]


def test_snapshot() -> None:
    service = OptimizerService()
    service.optimize(["a", "b"], lambda value: float(len(value)))
    snapshot = service.snapshot()
    assert snapshot["name"] == "optimizer"
    assert snapshot["runs"] == 1
    assert snapshot["last_result"]["selected"] == "a"


def test_health_lifecycle() -> None:
    service = OptimizerService()
    assert service.health().severity == Severity.LOW
    service.start()
    assert service.health().healthy
    assert service.health().severity == Severity.INFO
    service.suspend()
    assert service.health().degraded
    assert service.health().severity == Severity.MEDIUM
    service.resume()
    service.terminate()
    assert service.health().unhealthy
    assert service.health().severity == Severity.HIGH
