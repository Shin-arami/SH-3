from __future__ import annotations

from datetime import UTC
from typing import Any, cast

import pytest

from foundation.enums import LifecycleState
from services.learning import (
    LearningRecord,
    LearningService,
)


def test_default_state() -> None:
    service = LearningService()
    assert service.state == LifecycleState.CREATED
    assert service.count() == 0


def test_record() -> None:
    service = LearningService()
    record = service.record(
        "planner",
        0.8,
        True,
        {"episode": 1},
    )
    assert record.key == "planner"
    assert record.value == 0.8
    assert record.success is True
    assert record.details["episode"] == 1
    assert service.count("planner") == 1


def test_record_details_are_isolated() -> None:
    details = {"score": 1}
    service = LearningService()
    record = service.record("planner", 1.0, details=details)
    details["score"] = 2
    assert record.details["score"] == 1


def test_record_is_immutable() -> None:
    record = LearningRecord("planner", 1.0, True)
    with pytest.raises((AttributeError, TypeError)):
        cast(Any, record).value = 2.0


def test_record_timestamp_is_utc_aware() -> None:
    record = LearningRecord("planner", 1.0, True)
    assert record.timestamp.tzinfo is not None
    assert record.timestamp.utcoffset() is not None
    assert record.timestamp.tzinfo == UTC


def test_latest_and_average() -> None:
    service = LearningService()
    service.record("planner", 1.0)
    service.record("planner", 3.0)
    assert service.latest("planner") is not None
    record = service.latest("planner")
    assert record is not None
    assert record.value == 3.0
    assert service.average("planner") == 2.0


def test_success_rate() -> None:
    service = LearningService()
    service.record("planner", 1.0, True)
    service.record("planner", 0.0, False)
    service.record("planner", 1.0, True)
    assert service.success_rate("planner") == pytest.approx(2 / 3)


def test_records_and_keys_are_deterministic() -> None:
    service = LearningService()
    service.record("z", 1.0)
    service.record("a", 2.0)
    assert service.keys() == ("a", "z")
    assert len(service.records()) == 2


def test_clear() -> None:
    service = LearningService()
    service.record("planner", 1.0)
    service.record("memory", 2.0)
    service.clear("planner")
    assert service.count("planner") == 0
    assert service.count("memory") == 1
    service.clear()
    assert service.count() == 0


def test_snapshot() -> None:
    service = LearningService()
    service.record("planner", 0.75, True, {"episode": 4})
    snapshot = service.snapshot()
    assert snapshot["name"] == "learning"
    assert snapshot["state"] == LifecycleState.CREATED.value
    assert snapshot["record_count"] == 1
    assert snapshot["keys"] == ("planner",)
    assert snapshot["records"]["planner"][0]["value"] == 0.75


def test_lifecycle_and_health() -> None:
    service = LearningService()
    assert service.health().state == "UNKNOWN"
    service.start()
    assert service.health().healthy
    service.suspend()
    assert service.health().degraded
    service.resume()
    assert service.health().healthy
    service.terminate()
    assert service.health().unhealthy
