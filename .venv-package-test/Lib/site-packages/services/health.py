from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from foundation.enums import Severity

__all__ = [
    "HealthCheckableProtocol",
    "HealthModel",
    "HealthState",
    "HealthStatus",
]


class HealthState(StrEnum):
    UNKNOWN = "UNKNOWN"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


@dataclass(frozen=True, slots=True)
class HealthStatus:
    state: HealthState = HealthState.UNKNOWN
    message: str = ""
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    details: Mapping[str, Any] = field(default_factory=dict)
    service: str = ""
    severity: Severity = Severity.LOW

    def __post_init__(self) -> None:
        if not isinstance(self.state, HealthState):
            raise TypeError("state must be a HealthState")
        if not isinstance(self.checked_at, datetime):
            raise TypeError("checked_at must be a datetime")
        if self.checked_at.tzinfo is None:
            raise ValueError("checked_at must be timezone-aware")
        if not isinstance(self.severity, Severity):
            raise TypeError("severity must be a Severity")
        object.__setattr__(
            self,
            "details",
            MappingProxyType(dict(self.details)),
        )

    @property
    def healthy(self) -> bool:
        return self.state == HealthState.HEALTHY

    @property
    def degraded(self) -> bool:
        return self.state == HealthState.DEGRADED

    @property
    def unhealthy(self) -> bool:
        return self.state == HealthState.UNHEALTHY

    @property
    def unknown(self) -> bool:
        return self.state == HealthState.UNKNOWN

    @classmethod
    def create(
        cls,
        state: HealthState = HealthState.UNKNOWN,
        message: str = "",
        details: Mapping[str, object] | None = None,
        service: str = "",
        severity: Severity | None = None,
    ) -> HealthStatus:
        if not isinstance(state, HealthState):
            raise TypeError("state must be a HealthState")
        if severity is None:
            severity = {
                HealthState.HEALTHY: Severity.INFO,
                HealthState.DEGRADED: Severity.MEDIUM,
                HealthState.UNHEALTHY: Severity.HIGH,
                HealthState.UNKNOWN: Severity.LOW,
            }[state]
        return cls(
            state=state,
            message=message,
            checked_at=datetime.now(UTC),
            details={} if details is None else details,
            service=service,
            severity=severity,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "message": self.message,
            "checked_at": self.checked_at.isoformat(),
            "details": dict(self.details),
            "service": self.service,
            "severity": self.severity.value,
        }


@runtime_checkable
class HealthCheckableProtocol(Protocol):
    def health(self) -> HealthStatus: ...


class HealthModel:
    __slots__ = ("_status", "service")

    def __init__(self, service: str = "") -> None:
        self.service = service
        self._status = HealthStatus.create(service=service)

    @property
    def status(self) -> HealthStatus:
        return self._status

    @property
    def state(self) -> HealthState:
        return self._status.state

    @property
    def healthy(self) -> bool:
        return self._status.healthy

    @property
    def degraded(self) -> bool:
        return self._status.degraded

    @property
    def unhealthy(self) -> bool:
        return self._status.unhealthy

    @property
    def is_unknown(self) -> bool:
        return self._status.unknown

    def set(
        self,
        state: HealthState,
        message: str = "",
        details: Mapping[str, Any] | None = None,
    ) -> HealthStatus:
        self._status = HealthStatus.create(
            state=state,
            message=message,
            details={} if details is None else details,
            service=self.service,
        )
        return self._status

    def healthy_status(
        self,
        message: str = "",
        details: Mapping[str, Any] | None = None,
    ) -> HealthStatus:
        return self.set(HealthState.HEALTHY, message, details)

    def degraded_status(
        self,
        message: str = "",
        details: Mapping[str, Any] | None = None,
    ) -> HealthStatus:
        return self.set(HealthState.DEGRADED, message, details)

    def unhealthy_status(
        self,
        message: str = "",
        details: Mapping[str, Any] | None = None,
    ) -> HealthStatus:
        return self.set(HealthState.UNHEALTHY, message, details)

    def unknown(
        self,
        message: str = "",
        details: Mapping[str, Any] | None = None,
    ) -> HealthStatus:
        return self.set(HealthState.UNKNOWN, message, details)

    def health(self) -> HealthStatus:
        return self._status

    def snapshot(self) -> dict[str, Any]:
        return self._status.to_dict()
