from __future__ import annotations

import pytest

from foundation.enums import LifecycleState
from services.base import Service, ServiceException
from services.manager import ServiceManager


class DummyManagerService(Service):
    def __init__(self, name: str) -> None:
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


def test_register() -> None:
    manager = ServiceManager()
    service = DummyManagerService("planner")
    manager.register(service)
    assert len(manager) == 1
    assert manager.get("planner") is service


def test_register_rejects_duplicate() -> None:
    manager = ServiceManager()
    manager.register(DummyManagerService("planner"))
    with pytest.raises(ServiceException):
        manager.register(DummyManagerService("planner"))


def test_register_rejects_invalid_type() -> None:
    manager = ServiceManager()
    with pytest.raises(TypeError):
        manager.register(object())  # type: ignore[arg-type]


def test_get_missing_service() -> None:
    manager = ServiceManager()
    with pytest.raises(ServiceException):
        manager.get("missing")


def test_get_optional_missing_service() -> None:
    manager = ServiceManager()
    assert manager.get_optional("missing") is None


def test_contains() -> None:
    manager = ServiceManager()
    manager.register(DummyManagerService("planner"))
    assert manager.contains("planner")
    assert "planner" in manager
    assert not manager.contains("memory")


def test_names_preserve_registration_order() -> None:
    manager = ServiceManager()
    manager.register(DummyManagerService("planner"))
    manager.register(DummyManagerService("memory"))
    manager.register(DummyManagerService("policy"))
    assert manager.names() == ("planner", "memory", "policy")


def test_services_preserve_registration_order() -> None:
    manager = ServiceManager()
    first = DummyManagerService("first")
    second = DummyManagerService("second")
    manager.register(first)
    manager.register(second)
    assert manager.services() == (first, second)


def test_unregister() -> None:
    manager = ServiceManager()
    service = DummyManagerService("planner")
    manager.register(service)
    removed = manager.unregister("planner")
    assert removed is service
    assert len(manager) == 0


def test_unregister_missing_returns_none() -> None:
    manager = ServiceManager()
    assert manager.unregister("missing") is None


def test_start() -> None:
    manager = ServiceManager()
    service = DummyManagerService("planner")
    manager.register(service)
    manager.start("planner")
    assert service.state == LifecycleState.ACTIVE


def test_suspend_and_resume() -> None:
    manager = ServiceManager()
    service = DummyManagerService("planner")
    manager.register(service)
    manager.start("planner")
    manager.suspend("planner")
    assert service.state == LifecycleState.SUSPENDED
    manager.resume("planner")
    assert service.state.name == "ACTIVE"
    assert service.active


def test_terminate() -> None:
    manager = ServiceManager()
    service = DummyManagerService("planner")
    manager.register(service)
    manager.start("planner")
    manager.terminate("planner")
    assert service.state == LifecycleState.TERMINATED


def test_start_all() -> None:
    manager = ServiceManager()
    first = DummyManagerService("first")
    second = DummyManagerService("second")
    manager.register(first)
    manager.register(second)
    manager.start_all()
    assert first.active
    assert second.active
    assert first.calls == ["start"]
    assert second.calls == ["start"]


def test_suspend_all() -> None:
    manager = ServiceManager()
    first = DummyManagerService("first")
    second = DummyManagerService("second")
    manager.register(first)
    manager.register(second)
    manager.start_all()
    manager.suspend_all()
    assert first.suspended
    assert second.suspended


def test_resume_all() -> None:
    manager = ServiceManager()
    first = DummyManagerService("first")
    second = DummyManagerService("second")
    manager.register(first)
    manager.register(second)
    manager.start_all()
    manager.suspend_all()
    manager.resume_all()
    assert first.active
    assert second.active


def test_terminate_all() -> None:
    manager = ServiceManager()
    first = DummyManagerService("first")
    second = DummyManagerService("second")
    manager.register(first)
    manager.register(second)
    manager.start_all()
    manager.terminate_all()
    assert first.terminated
    assert second.terminated


def test_bulk_operations_respect_current_state() -> None:
    manager = ServiceManager()
    created = DummyManagerService("created")
    active = DummyManagerService("active")
    suspended = DummyManagerService("suspended")
    terminated = DummyManagerService("terminated")

    manager.register(created)
    manager.register(active)
    manager.register(suspended)
    manager.register(terminated)

    active.start()
    suspended.start()
    suspended.suspend()
    terminated.terminate()

    manager.suspend_all()

    assert created.state == LifecycleState.CREATED
    assert active.state == LifecycleState.SUSPENDED
    assert suspended.state == LifecycleState.SUSPENDED
    assert terminated.state == LifecycleState.TERMINATED


def test_clear() -> None:
    manager = ServiceManager()
    manager.register(DummyManagerService("planner"))
    manager.register(DummyManagerService("memory"))
    manager.clear()
    assert len(manager) == 0
    assert manager.names() == ()


def test_iteration() -> None:
    manager = ServiceManager()
    first = DummyManagerService("first")
    second = DummyManagerService("second")
    manager.register(first)
    manager.register(second)
    assert tuple(manager) == (first, second)


def test_snapshot() -> None:
    manager = ServiceManager()
    service = DummyManagerService("planner")
    manager.register(service)
    service.start()

    snapshot = manager.snapshot()

    assert snapshot["count"] == 1
    assert snapshot["services"]["planner"]["state"] == "ACTIVE"
    assert snapshot["services"]["planner"]["active"] is True
