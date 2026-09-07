from __future__ import annotations

from typing import Any

from foundation.enums import LifecycleState
from services import (
    ExecutableServiceProtocol,
    HealthCheckableProtocol,
    Service,
    ServiceProtocol,
)


class ProtocolService(Service):
    def _on_start(self) -> None:
        pass


class ExecutableService:
    def execute(self, value: int, *, multiplier: int = 1) -> int:
        return value * multiplier


class HealthService:
    def health(self) -> dict[str, Any]:
        return {"healthy": True}


def test_service_implements_service_protocol() -> None:
    service = ProtocolService("test")
    assert isinstance(service, ServiceProtocol)


def test_service_protocol_state() -> None:
    service = ProtocolService("test")
    assert service.state == LifecycleState.CREATED
    service.start()
    assert service.active
    service.suspend()
    assert service.suspended
    service.resume()
    assert service.active
    service.terminate()
    assert service.terminated


def test_executable_protocol() -> None:
    service = ExecutableService()
    assert isinstance(service, ExecutableServiceProtocol)
    assert service.execute(3, multiplier=4) == 12


def test_health_protocol() -> None:
    service = HealthService()
    assert isinstance(service, HealthCheckableProtocol)
    assert service.health() == {"healthy": True}


def test_protocols_are_structural() -> None:
    class StructuralService:
        name = "structural"
        state = LifecycleState.CREATED
        active = False
        suspended = False
        terminated = False

        def start(self) -> None:
            pass

        def suspend(self) -> None:
            pass

        def resume(self) -> None:
            pass

        def terminate(self) -> None:
            pass

        def snapshot(self) -> dict[str, Any]:
            return {"name": self.name}

    assert isinstance(StructuralService(), ServiceProtocol)
