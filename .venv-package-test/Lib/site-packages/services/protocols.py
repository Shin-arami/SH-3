from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from foundation.enums import LifecycleState

from .health import HealthStatus

__all__ = [
    "ExecutableServiceProtocol",
    "HealthCheckableProtocol",
    "ServiceProtocol",
]


@runtime_checkable
class ServiceProtocol(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def state(self) -> LifecycleState: ...

    @property
    def active(self) -> bool: ...

    @property
    def suspended(self) -> bool: ...

    @property
    def terminated(self) -> bool: ...

    def start(self) -> None: ...

    def suspend(self) -> None: ...

    def resume(self) -> None: ...

    def terminate(self) -> None: ...

    def snapshot(self) -> dict[str, Any]: ...


@runtime_checkable
class ExecutableServiceProtocol(Protocol):
    def execute(self, *args: Any, **kwargs: Any) -> Any: ...


@runtime_checkable
class HealthCheckableProtocol(Protocol):
    def health(self) -> HealthStatus: ...
