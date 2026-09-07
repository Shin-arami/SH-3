from __future__ import annotations

from collections.abc import Iterator
from threading import RLock
from typing import Any

from foundation.enums import LifecycleState
from foundation.utils.logging import info

from .base import Service, ServiceException

__all__ = ["ServiceManager"]


class ServiceManager:
    __slots__ = ("_lock", "_services")

    def __init__(self) -> None:
        self._services: dict[str, Service] = {}
        self._lock = RLock()

    def register(self, service: Service) -> None:
        if not isinstance(service, Service):
            raise TypeError("service must be a Service")
        with self._lock:
            if service.name in self._services:
                raise ServiceException(f"Service already registered: {service.name}")
            self._services[service.name] = service
            info(
                "Service registered",
                {
                    "service": service.name,
                    "state": service.state.value,
                },
            )

    def unregister(self, name: str) -> Service | None:
        with self._lock:
            service = self._services.pop(name, None)
            if service is not None:
                info("Service unregistered", {"service": name})
            return service

    def get(self, name: str) -> Service:
        with self._lock:
            service = self._services.get(name)
            if service is None:
                raise ServiceException(f"Service not found: {name}")
            return service

    def get_optional(self, name: str) -> Service | None:
        with self._lock:
            return self._services.get(name)

    def contains(self, name: str) -> bool:
        with self._lock:
            return name in self._services

    def names(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._services)

    def services(self) -> tuple[Service, ...]:
        with self._lock:
            return tuple(self._services.values())

    def start(self, name: str) -> None:
        service = self.get(name)
        service.start()

    def suspend(self, name: str) -> None:
        service = self.get(name)
        service.suspend()

    def resume(self, name: str) -> None:
        service = self.get(name)
        service.resume()

    def terminate(self, name: str) -> None:
        service = self.get(name)
        service.terminate()

    def start_all(self) -> None:
        for service in self.services():
            service.start()

    def suspend_all(self) -> None:
        for service in self.services():
            if service.state == LifecycleState.ACTIVE:
                service.suspend()

    def resume_all(self) -> None:
        for service in self.services():
            if service.state == LifecycleState.SUSPENDED:
                service.resume()

    def terminate_all(self) -> None:
        for service in self.services():
            if service.state != LifecycleState.TERMINATED:
                service.terminate()

    def clear(self) -> None:
        with self._lock:
            self._services.clear()
            info("Service registry cleared")

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            services = tuple(self._services.values())
            return {
                "count": len(services),
                "services": {service.name: service.snapshot() for service in services},
            }

    def __contains__(self, name: object) -> bool:
        with self._lock:
            return name in self._services

    def __len__(self) -> int:
        with self._lock:
            return len(self._services)

    def __iter__(self) -> Iterator[Service]:
        with self._lock:
            return iter(tuple(self._services.values()))
