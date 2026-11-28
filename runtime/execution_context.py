from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

__all__ = ["ExecutionContext"]


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    execution_id: str
    correlation_id: str | None
    causation_id: str | None
    trace_id: str | None
    tenant_id: str | None
    attempt: int
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.execution_id, str) or not self.execution_id:
            raise ValueError("execution_id must not be empty")
        for name in ("correlation_id", "causation_id", "trace_id", "tenant_id"):
            value = getattr(self, name)
            if value is not None and not value:
                raise ValueError(f"{name} must not be empty")
        if not isinstance(self.attempt, int) or self.attempt < 0:
            raise ValueError("attempt must be >= 0")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @classmethod
    def create(
        cls,
        *,
        execution_id: str,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        tenant_id: str | None = None,
        attempt: int = 0,
        metadata: Mapping[str, Any] | None = None,
    ) -> ExecutionContext:
        return cls(
            execution_id=execution_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            trace_id=trace_id,
            tenant_id=tenant_id,
            attempt=attempt,
            metadata=metadata or {},
        )

    def next_attempt(self) -> ExecutionContext:
        return ExecutionContext(
            execution_id=self.execution_id,
            correlation_id=self.correlation_id,
            causation_id=self.causation_id,
            trace_id=self.trace_id,
            tenant_id=self.tenant_id,
            attempt=self.attempt + 1,
            metadata=self.metadata,
        )

    def with_causation(self, causation_id: str) -> ExecutionContext:
        if not causation_id:
            raise ValueError("causation_id must not be empty")
        return ExecutionContext(
            execution_id=self.execution_id,
            correlation_id=self.correlation_id,
            causation_id=causation_id,
            trace_id=self.trace_id,
            tenant_id=self.tenant_id,
            attempt=self.attempt,
            metadata=self.metadata,
        )
