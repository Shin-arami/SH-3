from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, unique
from types import MappingProxyType
from typing import Any

from foundation.Enums.priority import Priority
from foundation.version import EVENT_SCHEMA_VERSION
from runtime.execution_context import ExecutionContext

__all__ = ["ExecutionRequest", "ExecutionSnapshot", "ExecutionState"]


@unique
class ExecutionState(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"

    @property
    def terminal(self) -> bool:
        return self in {
            ExecutionState.COMPLETED,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED,
            ExecutionState.TIMED_OUT,
        }


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    execution_id: str
    operation: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    priority: Priority = Priority.NORMAL
    timeout: float | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.execution_id:
            raise ValueError("execution_id must not be empty")
        if not self.operation:
            raise ValueError("operation must not be empty")
        if not isinstance(self.priority, Priority):
            raise TypeError("priority must be Priority")
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        for name, value in (
            ("correlation_id", self.correlation_id),
            ("causation_id", self.causation_id),
            ("trace_id", self.trace_id),
            ("tenant_id", self.tenant_id),
        ):
            if value is not None and not value:
                raise ValueError(f"{name} must not be empty")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @classmethod
    def create(
        cls,
        execution_id: str,
        operation: str,
        *,
        payload: Mapping[str, Any] | None = None,
        priority: Priority = Priority.NORMAL,
        timeout: float | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        tenant_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ExecutionRequest:
        return cls(
            execution_id=execution_id,
            operation=operation,
            payload=payload or {},
            priority=priority,
            timeout=timeout,
            correlation_id=correlation_id or execution_id,
            causation_id=causation_id,
            trace_id=trace_id,
            tenant_id=tenant_id,
            metadata=metadata or {},
        )

    @property
    def context(self) -> ExecutionContext:
        return ExecutionContext.create(
            execution_id=self.execution_id,
            correlation_id=self.correlation_id,
            causation_id=self.causation_id,
            trace_id=self.trace_id,
            tenant_id=self.tenant_id,
            attempt=0,
            metadata=self.metadata,
        )


@dataclass(frozen=True, slots=True)
class ExecutionSnapshot:
    execution_id: str
    operation: str
    state: ExecutionState
    priority: Priority
    created_at: datetime
    queued_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    timeout: float | None = None
    attempt: int = 0
    result: Any = None
    error_type: str | None = None
    error_message: str | None = None
    correlation_id: str = ""
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    event_schema_version: str = EVENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.execution_id:
            raise ValueError("execution_id must not be empty")
        if not self.operation:
            raise ValueError("operation must not be empty")
        if not isinstance(self.state, ExecutionState):
            raise TypeError("state must be ExecutionState")
        if not isinstance(self.priority, Priority):
            raise TypeError("priority must be Priority")
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if not self.correlation_id:
            raise ValueError("correlation_id must not be empty")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        for name in ("created_at", "queued_at", "started_at", "completed_at"):
            value = getattr(self, name)
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{name} must be timezone-aware")
        for name, value in (
            ("causation_id", self.causation_id),
            ("trace_id", self.trace_id),
            ("tenant_id", self.tenant_id),
        ):
            if value is not None and not value:
                raise ValueError(f"{name} must not be empty")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

        timestamps = (
            ("queued_at", self.queued_at, "created_at", self.created_at),
            ("started_at", self.started_at, "queued_at", self.queued_at),
            ("completed_at", self.completed_at, "started_at", self.started_at),
        )
        for current_name, current, previous_name, previous in timestamps:
            if current is not None and previous is not None and current < previous:
                raise ValueError(f"{current_name} must be >= {previous_name}")
        if self.attempt < 0:
            raise ValueError("attempt must be >= 0")


    @classmethod
    def create(
        cls,
        request: ExecutionRequest,
        *,
        now: datetime | None = None,
    ) -> ExecutionSnapshot:
        if not isinstance(request, ExecutionRequest):
            raise TypeError("request must be ExecutionRequest")
        timestamp = now or datetime.now(UTC)
        if timestamp.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        return cls(
            execution_id=request.execution_id,
            operation=request.operation,
            state=ExecutionState.CREATED,
            priority=request.priority,
            created_at=timestamp,
            timeout=request.timeout,
            correlation_id=request.correlation_id or request.execution_id,
            causation_id=request.causation_id,
            trace_id=request.trace_id,
            tenant_id=request.tenant_id,
            metadata=request.metadata,
        )

    @property
    def terminal(self) -> bool:
        return self.state.terminal

    @property
    def context(self) -> ExecutionContext:
        return ExecutionContext.create(
            execution_id=self.execution_id,
            correlation_id=self.correlation_id,
            causation_id=self.causation_id,
            trace_id=self.trace_id,
            tenant_id=self.tenant_id,
            attempt=self.attempt,
            metadata=self.metadata,
        )
