from __future__ import annotations

from datetime import UTC, datetime

import pytest

from services.health import (
    HealthCheckableProtocol,
    HealthModel,
    HealthState,
    HealthStatus,
)


def test_default_status_is_unknown() -> None:
    model = HealthModel("planner")
    assert model.state == HealthState.UNKNOWN
    assert not model.healthy
    assert not model.degraded
    assert not model.unhealthy


def test_health_status_is_immutable() -> None:
    status = HealthStatus()
    with pytest.raises((AttributeError, TypeError)):
        status.state = HealthState.HEALTHY  # type: ignore[misc]


def test_status_requires_timezone_aware_datetime() -> None:
    with pytest.raises(ValueError):
        HealthStatus(checked_at=datetime.now())


def test_status_properties() -> None:
    assert HealthStatus(HealthState.HEALTHY).healthy
    assert HealthStatus(HealthState.DEGRADED).degraded
    assert HealthStatus(HealthState.UNHEALTHY).unhealthy


def test_status_to_dict() -> None:
    checked_at = datetime.now(UTC)
    status = HealthStatus(
        state=HealthState.HEALTHY,
        message="ready",
        checked_at=checked_at,
        details={"latency_ms": 2},
    )
    result = status.to_dict()
    assert result == {
        "state": "HEALTHY",
        "message": "ready",
        "checked_at": checked_at.isoformat(),
        "details": {"latency_ms": 2},
        "service": "",
        "severity": "LOW",
    }


def test_status_details_are_isolated() -> None:
    details = {"value": 1}
    status = HealthStatus(details=details)
    details["value"] = 2
    assert status.details["value"] == 1


def test_create_generates_utc_timestamp() -> None:
    status = HealthStatus.create(HealthState.HEALTHY)
    assert status.checked_at.tzinfo is not None
    assert status.checked_at.utcoffset() == UTC.utcoffset(status.checked_at)


def test_set_updates_status() -> None:
    model = HealthModel("planner")
    status = model.set(
        HealthState.HEALTHY,
        "ready",
        {"component": "runtime"},
    )
    assert model.status is status
    assert model.state == HealthState.HEALTHY
    assert status.message == "ready"
    assert status.details["component"] == "runtime"


def test_state_helpers() -> None:
    model = HealthModel("planner")
    model.healthy_status("ready")
    assert model.healthy
    model.degraded_status("slow")
    assert model.degraded
    model.unhealthy_status("failed")
    assert model.unhealthy
    model.unknown()
    assert model.state == HealthState.UNKNOWN


def test_snapshot() -> None:
    model = HealthModel("planner")
    model.healthy_status("ready", {"version": "1"})
    snapshot = model.snapshot()
    assert snapshot["state"] == "HEALTHY"
    assert snapshot["message"] == "ready"
    assert snapshot["details"] == {"version": "1"}


def test_health_model_is_health_checkable() -> None:
    model = HealthModel("planner")
    assert isinstance(model, HealthCheckableProtocol)
    assert model.health().service == "planner"
