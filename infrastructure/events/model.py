"""
SH-3 Complete Edition v2.0
Infrastructure Layer
Events Subsystem

model.py

Canonical immutable event model.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.Enums.priority import Priority
from foundation.types.identifiers import IdentifierGenerator
from foundation.types.protocols import Serializable, Validatable

__all__ = [
    "Event",
    "EventContext",
    "EventMetadata",
]


@dataclass(frozen=True, slots=True)
class EventMetadata(Serializable, Validatable):
    event_id: str
    event_name: str
    event_version: str
    timestamp: datetime
    producer: str
    correlation_id: str
    causation_id: str | None = None
    priority: Priority = Priority.NORMAL
    tags: Mapping[str, str] = field(default_factory=dict)
    trace_id: str | None = None
    tenant_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tags",
            MappingProxyType(dict(self.tags)),
        )
        self.validate()

    def validate(self) -> None:
        if not self.event_id:
            raise ValueError("event_id must not be empty")
        if not self.event_name:
            raise ValueError("event_name must not be empty")
        if not self.event_version:
            raise ValueError("event_version must not be empty")
        if not self.producer:
            raise ValueError("producer must not be empty")
        if not self.correlation_id:
            raise ValueError("correlation_id must not be empty")
        if not isinstance(self.timestamp, datetime):
            raise TypeError("timestamp must be datetime")
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        if not isinstance(self.priority, Priority):
            raise TypeError("priority must be Priority")
        for key, value in self.tags.items():
            if not isinstance(key, str) or not key:
                raise TypeError("tag keys must be non-empty strings")
            if not isinstance(value, str):
                raise TypeError("tag values must be strings")

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_name": self.event_name,
            "event_version": self.event_version,
            "timestamp": self.timestamp.isoformat(),
            "producer": self.producer,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "priority": self.priority.name,
            "tags": dict(self.tags),
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EventMetadata:
        return cls(
            event_id=str(data["event_id"]),
            event_name=str(data["event_name"]),
            event_version=str(data["event_version"]),
            timestamp=datetime.fromisoformat(str(data["timestamp"])),
            producer=str(data["producer"]),
            correlation_id=str(data["correlation_id"]),
            causation_id=data.get("causation_id"),
            priority=Priority[str(data.get("priority", Priority.NORMAL.name))],
            tags=dict(data.get("tags", {})),
            trace_id=data.get("trace_id"),
            tenant_id=data.get("tenant_id"),
        )


@dataclass(frozen=True, slots=True)
class EventContext(Serializable, Validatable):
    runtime: Mapping[str, Any] = field(default_factory=dict)
    execution: Mapping[str, Any] = field(default_factory=dict)
    mission: Mapping[str, Any] = field(default_factory=dict)
    security: Mapping[str, Any] = field(default_factory=dict)
    tracing: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "runtime",
            MappingProxyType(dict(self.runtime)),
        )
        object.__setattr__(
            self,
            "execution",
            MappingProxyType(dict(self.execution)),
        )
        object.__setattr__(
            self,
            "mission",
            MappingProxyType(dict(self.mission)),
        )
        object.__setattr__(
            self,
            "security",
            MappingProxyType(dict(self.security)),
        )
        object.__setattr__(
            self,
            "tracing",
            MappingProxyType(dict(self.tracing)),
        )
        self.validate()

    def validate(self) -> None:
        for name in (
            "runtime",
            "execution",
            "mission",
            "security",
            "tracing",
        ):
            value = getattr(self, name)
            if not isinstance(value, Mapping):
                raise TypeError(f"{name} must be a mapping")

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime": dict(self.runtime),
            "execution": dict(self.execution),
            "mission": dict(self.mission),
            "security": dict(self.security),
            "tracing": dict(self.tracing),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EventContext:
        return cls(
            runtime=dict(data.get("runtime", {})),
            execution=dict(data.get("execution", {})),
            mission=dict(data.get("mission", {})),
            security=dict(data.get("security", {})),
            tracing=dict(data.get("tracing", {})),
        )


@dataclass(frozen=True, slots=True)
class Event(Serializable, Validatable):
    metadata: EventMetadata
    payload: Mapping[str, Any]
    context: EventContext
    category: Category = Category.RUNTIME
    event_type: EventType = EventType.UNKNOWN

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "payload",
            MappingProxyType(dict(self.payload)),
        )
        self.validate()

    @property
    def id(self) -> str:
        return self.metadata.event_id

    @property
    def name(self) -> str:
        return self.metadata.event_name

    @property
    def version(self) -> str:
        return self.metadata.event_version

    @property
    def priority(self) -> Priority:
        return self.metadata.priority

    @property
    def correlation_id(self) -> str:
        return self.metadata.correlation_id

    @property
    def trace_id(self) -> str | None:
        return self.metadata.trace_id

    @property
    def causation_id(self) -> str | None:
        return self.metadata.causation_id

    @property
    def timestamp(self) -> datetime:
        return self.metadata.timestamp

    def validate(self) -> None:
        if not isinstance(self.metadata, EventMetadata):
            raise TypeError("metadata must be EventMetadata")
        if not isinstance(self.context, EventContext):
            raise TypeError("context must be EventContext")
        if not isinstance(self.payload, Mapping):
            raise TypeError("payload must be a mapping")
        if not isinstance(self.category, Category):
            raise TypeError("category must be Category")
        if not isinstance(self.event_type, EventType):
            raise TypeError("event_type must be EventType")

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "payload": dict(self.payload),
            "context": self.context.to_dict(),
            "category": self.category.value,
            "event_type": self.event_type.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        return cls(
            metadata=EventMetadata.from_dict(data["metadata"]),
            payload=dict(data["payload"]),
            context=EventContext.from_dict(data["context"]),
            category=Category(str(data.get("category", Category.RUNTIME.value))),
            event_type=EventType(str(data.get("event_type", EventType.UNKNOWN.value))),
        )

    @classmethod
    def create(
        cls,
        *,
        event_name: str,
        producer: str,
        payload: Mapping[str, Any] | None = None,
        category: Category = Category.RUNTIME,
        event_type: EventType = EventType.UNKNOWN,
        event_version: str = "1.0.0",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        priority: Priority = Priority.NORMAL,
        tags: Mapping[str, str] | None = None,
        trace_id: str | None = None,
        tenant_id: str | None = None,
        context: EventContext | None = None,
    ) -> Event:
        event_id = IdentifierGenerator.entity()
        correlation = correlation_id or event_id
        timestamp = datetime.now(UTC)

        metadata = EventMetadata(
            event_id=event_id,
            event_name=event_name,
            event_version=event_version,
            timestamp=timestamp,
            producer=producer,
            correlation_id=correlation,
            causation_id=causation_id,
            priority=priority,
            tags=tags or {},
            trace_id=trace_id,
            tenant_id=tenant_id,
        )

        return cls(
            metadata=metadata,
            payload=payload or {},
            context=context or EventContext(),
            category=category,
            event_type=event_type,
        )
