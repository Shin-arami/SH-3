from __future__ import annotations

import pytest

from foundation.enums import LifecycleState, Severity
from services.base import Service, ServiceException
from services.health import HealthStatus


class DummyService(Service):
    def __init__(self, name: str = "test") -> None:
        super().__init__(name)
        self.calls: list[str] = []

    def _on_start(self) -> None:
        self.calls.append("start")

    def _on_suspend(self) -> None:
        self.calls.append("suspend")

    def _on_resume(self) -> None:
        self.calls.append("resume")

    def _on_terminate(self) -> None:
        self.calls.append("terminate")


def test_initial_state() -> None:
    service = DummyService()
    assert service.state == LifecycleState.CREATED
    assert not service.active


def test_start() -> None:
    service = DummyService()
    service.start()
    assert service.state.name == "ACTIVE"
    assert service.active
    assert service.calls == ["start"]


def test_suspend_and_resume() -> None:
    service = DummyService()
    service.start()
    service.suspend()
    assert service.state == LifecycleState.SUSPENDED
    assert service.suspended
    service.resume()
    assert service.state.name == "ACTIVE"
    assert service.active
    assert service.calls == ["start", "suspend", "resume"]


def test_terminate_from_created() -> None:
    service = DummyService()
    service.terminate()
    assert service.state == LifecycleState.TERMINATED


def test_terminate_from_active() -> None:
    service = DummyService()
    service.start()
    service.terminate()
    assert service.terminated
    assert service.calls == ["start", "terminate"]


def test_terminate_from_suspended() -> None:
    service = DummyService()
    service.start()
    service.suspend()
    service.terminate()
    assert service.terminated
    assert service.calls == ["start", "suspend", "terminate"]


def test_invalid_start() -> None:
    service = DummyService()
    service.start()
    with pytest.raises(ServiceException):
        service.start()


def test_invalid_suspend() -> None:
    service = DummyService()
    with pytest.raises(ServiceException):
        service.suspend()


def test_invalid_resume() -> None:
    service = DummyService()
    with pytest.raises(ServiceException):
        service.resume()


def test_invalid_resume_after_termination() -> None:
    service = DummyService()
    service.terminate()
    with pytest.raises(ServiceException):
        service.resume()


def test_terminate_is_idempotent() -> None:
    service = DummyService()
    service.terminate()
    service.terminate()
    assert service.state == LifecycleState.TERMINATED


def test_empty_name_rejected() -> None:
    with pytest.raises(ValueError):
        DummyService("")


def test_snapshot() -> None:
    service = DummyService("planner")
    service.start()
    assert service.snapshot() == {
        "name": "planner",
        "state": "ACTIVE",
        "active": True,
        "suspended": False,
        "terminated": False,
    }


##
def test_health_created() -> None:
    service = DummyService("planner")
    health = service.health()

    assert isinstance(health, HealthStatus)
    assert health.service == "planner"
    assert health.healthy is False
    assert health.details["state"] == "CREATED"


def test_health_active() -> None:
    service = DummyService("planner")
    service.start()

    health = service.health()

    assert health.healthy is True
    assert health.severity == Severity.INFO
    assert health.details["state"] == "ACTIVE"


def test_health_suspended() -> None:
    service = DummyService("planner")
    service.start()
    service.suspend()

    health = service.health()

    assert health.healthy is False
    assert health.severity == Severity.MEDIUM
    assert health.details["state"] == "SUSPENDED"


def test_health_terminated() -> None:
    service = DummyService("planner")
    service.terminate()

    health = service.health()

    assert health.healthy is False
    assert health.severity == Severity.HIGH
    assert health.details["state"] == "TERMINATED"
