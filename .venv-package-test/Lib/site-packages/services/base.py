from __future__ import annotations

from abc import ABC, abstractmethod
from threading import RLock
from typing import Any

from foundation.enums import LifecycleState, Severity
from foundation.utils.exceptions import SH3Exception
from foundation.utils.logging import error, info

from .health import HealthState, HealthStatus

__all__ = ["Service", "ServiceException"]


class ServiceException(SH3Exception):
    """Service lifecycle or execution failure."""


class Service(ABC):
    __slots__ = ("_lock", "_state", "name")

    def __init__(self, name: str) -> None:
        if not name or not name.strip():
            raise ValueError("name must not be empty")
        self.name = name
        self._state = LifecycleState.CREATED
        self._lock = RLock()

    @property
    def state(self) -> LifecycleState:
        with self._lock:
            return self._state

    @property
    def active(self) -> bool:
        return self.state == LifecycleState.ACTIVE

    @property
    def suspended(self) -> bool:
        return self.state == LifecycleState.SUSPENDED

    @property
    def terminated(self) -> bool:
        return self.state == LifecycleState.TERMINATED

    def start(self) -> None:
        with self._lock:
            if self._state != LifecycleState.CREATED:
                raise ServiceException(
                    f"Cannot start service '{self.name}' from state {self._state.value}"
                )
            try:
                self._on_start()
                self._state = LifecycleState.ACTIVE
                info(
                    "Service started",
                    {"service": self.name, "state": self._state.value},
                )
            except SH3Exception:
                raise
            except Exception as exc:
                error(
                    "Service start failed",
                    {"service": self.name, "error": str(exc)},
                )
                raise ServiceException(f"Service start failed: {self.name}") from exc

    def suspend(self) -> None:
        with self._lock:
            if self._state != LifecycleState.ACTIVE:
                raise ServiceException(
                    f"Cannot suspend service '{self.name}' from state {self._state.value}"
                )
            try:
                self._on_suspend()
                self._state = LifecycleState.SUSPENDED
                info(
                    "Service suspended",
                    {"service": self.name, "state": self._state.value},
                )
            except SH3Exception:
                raise
            except Exception as exc:
                error(
                    "Service suspend failed",
                    {"service": self.name, "error": str(exc)},
                )
                raise ServiceException(f"Service suspend failed: {self.name}") from exc

    def resume(self) -> None:
        with self._lock:
            if self._state != LifecycleState.SUSPENDED:
                raise ServiceException(
                    f"Cannot resume service '{self.name}' from state {self._state.value}"
                )
            try:
                self._on_resume()
                self._state = LifecycleState.ACTIVE
                info(
                    "Service resumed",
                    {"service": self.name, "state": self._state.value},
                )
            except SH3Exception:
                raise
            except Exception as exc:
                error(
                    "Service resume failed",
                    {"service": self.name, "error": str(exc)},
                )
                raise ServiceException(f"Service resume failed: {self.name}") from exc

    def terminate(self) -> None:
        with self._lock:
            if self._state == LifecycleState.TERMINATED:
                return
            if self._state not in {
                LifecycleState.CREATED,
                LifecycleState.ACTIVE,
                LifecycleState.SUSPENDED,
            }:
                raise ServiceException(
                    f"Cannot terminate service '{self.name}' from state {self._state.value}"
                )
            try:
                self._on_terminate()
                self._state = LifecycleState.TERMINATED
                info(
                    "Service terminated",
                    {"service": self.name, "state": self._state.value},
                )
            except SH3Exception:
                raise
            except Exception as exc:
                error(
                    "Service termination failed",
                    {"service": self.name, "error": str(exc)},
                )
                raise ServiceException(f"Service termination failed: {self.name}") from exc

    def health(self) -> HealthStatus:
        with self._lock:
            state = self._state
        if state == LifecycleState.ACTIVE:
            return HealthStatus.create(
                HealthState.HEALTHY,
                "Service is active",
                {"state": state.value},
                self.name,
                Severity.INFO,
            )
        if state == LifecycleState.SUSPENDED:
            return HealthStatus.create(
                HealthState.DEGRADED,
                "Service is suspended",
                {"state": state.value},
                self.name,
                Severity.MEDIUM,
            )
        if state == LifecycleState.TERMINATED:
            return HealthStatus.create(
                HealthState.UNHEALTHY,
                "Service is terminated",
                {"state": state.value},
                self.name,
                Severity.HIGH,
            )
        return HealthStatus.create(
            HealthState.UNKNOWN,
            "Service is not active",
            {"state": state.value},
            self.name,
            Severity.LOW,
        )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "active": self._state == LifecycleState.ACTIVE,
                "suspended": self._state == LifecycleState.SUSPENDED,
                "terminated": self._state == LifecycleState.TERMINATED,
            }

    @abstractmethod
    def _on_start(self) -> None:
        """Initialize service resources."""
        return None

    def _on_suspend(self) -> None:
        """Suspend service resources."""
        return None

    def _on_resume(self) -> None:
        """Resume service resources."""
        return None

    def _on_terminate(self) -> None:
        """Release service resources."""
        return None
