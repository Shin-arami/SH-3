from __future__ import annotations

from dataclasses import dataclass

from .model import Event

__all__ = ["EventPropagationContext"]


@dataclass(frozen=True, slots=True)
class EventPropagationContext:
    correlation_id: str
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None

    def __post_init__(self) -> None:
        if not self.correlation_id:
            raise ValueError("correlation_id must not be empty")
        for name in ("causation_id", "trace_id", "tenant_id"):
            value = getattr(self, name)
            if value is not None and not value:
                raise ValueError(f"{name} must not be empty")

    @classmethod
    def create(
        cls,
        correlation_id: str,
        *,
        causation_id: str | None = None,
        trace_id: str | None = None,
        tenant_id: str | None = None,
    ) -> EventPropagationContext:
        return cls(
            correlation_id=correlation_id,
            causation_id=causation_id,
            trace_id=trace_id,
            tenant_id=tenant_id,
        )

    @classmethod
    def from_event(cls, event: Event) -> EventPropagationContext:
        if not isinstance(event, Event):
            raise TypeError("event must be Event")
        return cls(
            correlation_id=event.metadata.correlation_id,
            causation_id=event.metadata.event_id,
            trace_id=event.metadata.trace_id,
            tenant_id=event.metadata.tenant_id,
        )

    @classmethod
    def from_metadata(
        cls,
        *,
        correlation_id: str,
        event_id: str,
        trace_id: str | None = None,
        tenant_id: str | None = None,
    ) -> EventPropagationContext:
        return cls(
            correlation_id=correlation_id,
            causation_id=event_id,
            trace_id=trace_id,
            tenant_id=tenant_id,
        )

    def next(self, event_id: str) -> EventPropagationContext:
        if not event_id:
            raise ValueError("event_id must not be empty")
        return EventPropagationContext(
            correlation_id=self.correlation_id,
            causation_id=event_id,
            trace_id=self.trace_id,
            tenant_id=self.tenant_id,
        )

    def to_event_kwargs(self) -> dict[str, str]:
        result = {
            "correlation_id": self.correlation_id,
        }
        if self.causation_id is not None:
            result["causation_id"] = self.causation_id
        if self.trace_id is not None:
            result["trace_id"] = self.trace_id
        if self.tenant_id is not None:
            result["tenant_id"] = self.tenant_id
        return result
