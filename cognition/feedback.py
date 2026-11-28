from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, unique
from math import isfinite
from threading import RLock
from types import MappingProxyType
from typing import Any, Protocol

from foundation.utils.hash import short_id
from foundation.version import COGNITION_CONTRACT_VERSION, validate_semantic_version
from infrastructure.event_bus import EventBus, EventPublisher, EventSubscription
from infrastructure.events import Event

__all__ = [
    "CognitiveFeedback",
    "CognitiveFeedbackBridge",
    "CognitiveFeedbackKind",
    "CognitiveFeedbackStore",
]


@unique
class CognitiveFeedbackKind(StrEnum):
    CLOSED_LOOP = "closed_loop"
    LEARNING = "learning"
    OPTIMIZATION = "optimization"
    SELF_HEALING = "self_healing"


def _text(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _timestamp(name: str, value: object) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be datetime")
    if value.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


@dataclass(frozen=True, slots=True)
class CognitiveFeedback:
    feedback_id: str
    cycle_id: str
    goal_id: str
    kind: CognitiveFeedbackKind
    source_id: str
    success: bool
    score: float
    created_at: datetime
    reason: str
    correlation_id: str
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _text("feedback_id", self.feedback_id)
        _text("cycle_id", self.cycle_id)
        _text("goal_id", self.goal_id)
        if not isinstance(self.kind, CognitiveFeedbackKind):
            raise TypeError("kind must be CognitiveFeedbackKind")
        _text("source_id", self.source_id)
        if not isinstance(self.success, bool):
            raise TypeError("success must be bool")
        if not isinstance(self.score, (int, float)) or isinstance(self.score, bool):
            raise TypeError("score must be numeric")
        if not isfinite(float(self.score)) or not 0.0 <= float(self.score) <= 1.0:
            raise ValueError("score must be finite and between 0.0 and 1.0")
        _timestamp("created_at", self.created_at)
        _text("reason", self.reason)
        _text("correlation_id", self.correlation_id)
        for name, value in (("causation_id", self.causation_id), ("trace_id", self.trace_id), ("tenant_id", self.tenant_id)):
            if value is not None:
                _text(name, value)
        object.__setattr__(self, "score", float(self.score))
        object.__setattr__(self, "metadata", _mapping(self.metadata))

    @classmethod
    def create(
        cls,
        *,
        cycle_id: str,
        goal_id: str,
        kind: CognitiveFeedbackKind,
        source_id: str,
        success: bool,
        score: float,
        reason: str,
        correlation_id: str,
        causation_id: str | None = None,
        trace_id: str | None = None,
        tenant_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
        feedback_id: str | None = None,
        version: str = COGNITION_CONTRACT_VERSION,
    ) -> CognitiveFeedback:
        _text("version", version)
        validate_semantic_version(version, field="version")
        timestamp = created_at or datetime.now(UTC)
        resolved_id = feedback_id or short_id(
            {
                "cycle_id": cycle_id,
                "goal_id": goal_id,
                "kind": kind.value,
                "source_id": source_id,
                "success": success,
                "score": float(score),
                "reason": reason,
                "correlation_id": correlation_id,
                "causation_id": causation_id,
                "trace_id": trace_id,
                "tenant_id": tenant_id,
                "metadata": metadata or {},
                "created_at": timestamp.isoformat(),
                "version": version,
            },
            prefix="feedback:",
        )
        return cls(
            feedback_id=resolved_id,
            cycle_id=cycle_id,
            goal_id=goal_id,
            kind=kind,
            source_id=source_id,
            success=success,
            score=score,
            created_at=timestamp,
            reason=reason,
            correlation_id=correlation_id,
            causation_id=causation_id,
            trace_id=trace_id,
            tenant_id=tenant_id,
            metadata={**(metadata or {}), "version": version},
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CognitiveFeedback:
        if not isinstance(data, Mapping):
            raise TypeError("data must be a mapping")
        success = data.get("success")
        score = data.get("score")
        if not isinstance(success, bool):
            raise TypeError("success must be bool")
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            raise TypeError("score must be numeric")
        metadata_value = data.get("metadata")
        feedback_metadata = dict(metadata_value) if isinstance(metadata_value, Mapping) else {}
        return cls(
            feedback_id=_text("feedback_id", data.get("feedback_id")),
            cycle_id=_text("cycle_id", data.get("cycle_id")),
            goal_id=_text("goal_id", data.get("goal_id")),
            kind=CognitiveFeedbackKind(str(data.get("kind"))),
            source_id=_text("source_id", data.get("source_id")),
            success=success,
            score=float(score),
            created_at=_timestamp("created_at", datetime.fromisoformat(str(data.get("created_at")))),
            reason=_text("reason", data.get("reason")),
            correlation_id=_text("correlation_id", data.get("correlation_id")),
            causation_id=data.get("causation_id"),
            trace_id=data.get("trace_id"),
            tenant_id=data.get("tenant_id"),
            metadata=feedback_metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "cycle_id": self.cycle_id,
            "goal_id": self.goal_id,
            "kind": self.kind.value,
            "source_id": self.source_id,
            "success": self.success,
            "score": self.score,
            "created_at": self.created_at.isoformat(),
            "reason": self.reason,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "metadata": dict(self.metadata),
        }


class CognitiveFeedbackStore:
    __slots__ = ("_lock", "_records")

    def __init__(self) -> None:
        self._lock = RLock()
        self._records: dict[str, CognitiveFeedback] = {}

    def register(self, feedback: CognitiveFeedback) -> CognitiveFeedback:
        if not isinstance(feedback, CognitiveFeedback):
            raise TypeError("feedback must be CognitiveFeedback")
        with self._lock:
            existing = self._records.get(feedback.feedback_id)
            if existing is not None and existing != feedback:
                raise ValueError(f"conflicting feedback already registered: {feedback.feedback_id}")
            self._records[feedback.feedback_id] = feedback
            return existing or feedback

    def get(self, feedback_id: str) -> CognitiveFeedback | None:
        _text("feedback_id", feedback_id)
        with self._lock:
            return self._records.get(feedback_id)

    def records(self) -> tuple[CognitiveFeedback, ...]:
        with self._lock:
            return tuple(self._records.values())

    def for_goal(self, goal_id: str) -> tuple[CognitiveFeedback, ...]:
        _text("goal_id", goal_id)
        with self._lock:
            return tuple(record for record in self._records.values() if record.goal_id == goal_id)

    def latest(self) -> CognitiveFeedback | None:
        with self._lock:
            return max(self._records.values(), key=lambda record: (record.created_at, record.feedback_id), default=None)


class _FeedbackSink(Protocol):
    def record_feedback(self, feedback: CognitiveFeedback) -> CognitiveFeedback: ...


class CognitiveFeedbackBridge:
    __slots__ = ("_event_bus", "_event_publisher", "_sink", "_subscriber_id")

    def __init__(
        self,
        sink: _FeedbackSink,
        event_publisher: EventPublisher | None = None,
        *,
        subscriber_id: str = "cognition.feedback",
    ) -> None:
        if not callable(getattr(sink, "record_feedback", None)):
            raise TypeError("sink must provide record_feedback")
        if event_publisher is not None and not isinstance(event_publisher, EventPublisher):
            raise TypeError("event_publisher must be EventPublisher or None")
        self._sink = sink
        self._event_publisher = event_publisher
        self._event_bus: EventBus | None = None
        self._subscriber_id = _text("subscriber_id", subscriber_id)
        self._configure()

    def _configure(self) -> None:
        publisher = self._event_publisher
        event_bus = getattr(publisher, "event_bus", None) if publisher is not None else None
        if event_bus is not None and not isinstance(event_bus, EventBus):
            event_bus = None
        if self._event_bus is event_bus:
            return
        if self._event_bus is not None:
            with suppress(KeyError):
                self._event_bus.unsubscribe(self._subscriber_id)
        self._event_bus = event_bus
        if event_bus is None:
            return
        event_bus.subscribe(
            EventSubscription(
                subscriber_id=self._subscriber_id,
                handler=self._handle_event,
                event_name="CognitiveFeedbackRecorded",
                priority=100,
            ),
            replace=True,
        )

    def set_event_publisher(self, event_publisher: EventPublisher | None) -> None:
        if event_publisher is not None and not isinstance(event_publisher, EventPublisher):
            raise TypeError("event_publisher must be EventPublisher or None")
        self._event_publisher = event_publisher
        self._configure()

    def _handle_event(self, event: Event) -> None:
        payload = event.payload.get("feedback")
        if not isinstance(payload, Mapping):
            return
        try:
            self._sink.record_feedback(CognitiveFeedback.from_dict(payload))
        except Exception:
            return
