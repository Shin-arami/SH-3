from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from types import MappingProxyType
from typing import Any, Protocol

from cognition.feedback import CognitiveFeedback
from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.utils.hash import short_id
from foundation.utils.logging import error
from infrastructure.event_bus import EventBus, EventPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext

__all__ = [
    "CognitiveFeedbackBoundary",
    "CognitiveFeedbackRequest",
    "CognitiveFeedbackResult",
]


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


def _timestamp(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("created_at must be timezone-aware")
    return value.astimezone(UTC)


def _optional_text(name: str, value: object) -> str | None:
    if value is None:
        return None
    return _text(name, value)


class FeedbackBackend(Protocol):
    def record_feedback(self, feedback: CognitiveFeedback) -> CognitiveFeedback: ...


@dataclass(frozen=True, slots=True)
class CognitiveFeedbackRequest:
    request_id: str
    feedback: CognitiveFeedback
    created_at: datetime
    correlation_id: str
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _text("request_id", self.request_id)
        if not isinstance(self.feedback, CognitiveFeedback):
            raise TypeError("feedback must be CognitiveFeedback")
        object.__setattr__(self, "created_at", _timestamp(self.created_at))
        _text("correlation_id", self.correlation_id)
        for name, value in (("causation_id", self.causation_id), ("trace_id", self.trace_id), ("tenant_id", self.tenant_id)):
            _optional_text(name, value)
        object.__setattr__(self, "metadata", _mapping(self.metadata))

    @classmethod
    def from_feedback(
        cls,
        feedback: CognitiveFeedback,
        *,
        context: EventPropagationContext,
        created_at: datetime | None = None,
    ) -> CognitiveFeedbackRequest:
        if not isinstance(feedback, CognitiveFeedback):
            raise TypeError("feedback must be CognitiveFeedback")
        if not isinstance(context, EventPropagationContext):
            raise TypeError("context must be EventPropagationContext")
        request_id = short_id(
            {"feedback_id": feedback.feedback_id, "cycle_id": feedback.cycle_id},
            prefix="cognitive-feedback:",
        )
        return cls(
            request_id=request_id,
            feedback=feedback,
            created_at=created_at or feedback.created_at,
            correlation_id=context.correlation_id,
            causation_id=context.causation_id,
            trace_id=context.trace_id,
            tenant_id=context.tenant_id,
            metadata={"feedback_kind": feedback.kind.value},
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CognitiveFeedbackRequest:
        if not isinstance(data, Mapping):
            raise TypeError("data must be a mapping")
        created_at = data.get("created_at")
        timestamp = created_at if isinstance(created_at, datetime) else datetime.fromisoformat(str(created_at))
        feedback_data = data.get("feedback")
        if not isinstance(feedback_data, Mapping):
            raise TypeError("feedback must be a mapping")
        metadata = data.get("metadata")
        return cls(
            request_id=_text("request_id", data.get("request_id")),
            feedback=CognitiveFeedback.from_dict(feedback_data),
            created_at=timestamp,
            correlation_id=_text("correlation_id", data.get("correlation_id")),
            causation_id=data.get("causation_id"),
            trace_id=data.get("trace_id"),
            tenant_id=data.get("tenant_id"),
            metadata=metadata if isinstance(metadata, Mapping) else {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "feedback": self.feedback.to_dict(),
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class CognitiveFeedbackResult:
    request_id: str
    feedback_id: str
    success: bool
    created_at: datetime
    correlation_id: str
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        for name, value in (("request_id", self.request_id), ("feedback_id", self.feedback_id), ("correlation_id", self.correlation_id)):
            _text(name, value)
        if not isinstance(self.success, bool):
            raise TypeError("success must be bool")
        object.__setattr__(self, "created_at", _timestamp(self.created_at))
        _optional_text("causation_id", self.causation_id)
        _optional_text("trace_id", self.trace_id)
        _optional_text("tenant_id", self.tenant_id)
        _optional_text("error", self.error)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CognitiveFeedbackResult:
        if not isinstance(data, Mapping):
            raise TypeError("data must be a mapping")
        created_at = data.get("created_at")
        timestamp = created_at if isinstance(created_at, datetime) else datetime.fromisoformat(str(created_at))
        success = data.get("success")
        if not isinstance(success, bool):
            raise TypeError("success must be bool")
        return cls(
            request_id=_text("request_id", data.get("request_id")),
            feedback_id=_text("feedback_id", data.get("feedback_id")),
            success=success,
            created_at=timestamp,
            correlation_id=_text("correlation_id", data.get("correlation_id")),
            causation_id=data.get("causation_id"),
            trace_id=data.get("trace_id"),
            tenant_id=data.get("tenant_id"),
            error=data.get("error"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "feedback_id": self.feedback_id,
            "success": self.success,
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "error": self.error,
        }


class CognitiveFeedbackBoundary:
    __slots__ = ("_event_bus", "_event_publisher", "_last_context", "_lock", "_pending_requests", "_results", "_started", "_subscriber_id", "cognition")

    def __init__(
        self,
        cognition: FeedbackBackend,
        event_publisher: EventPublisher | None = None,
        *,
        subscriber_id: str = "cognition.feedback-boundary",
    ) -> None:
        if cognition is None:
            raise TypeError("cognition must not be None")
        if not callable(getattr(cognition, "record_feedback", None)):
            raise TypeError("cognition must provide record_feedback")
        if event_publisher is not None and not isinstance(event_publisher, EventPublisher):
            raise TypeError("event_publisher must be EventPublisher or None")
        self.cognition = cognition
        self._event_publisher = event_publisher
        self._event_bus: EventBus | None = None
        self._last_context: EventPropagationContext | None = None
        self._lock = RLock()
        self._pending_requests: set[str] = set()
        self._results: dict[str, CognitiveFeedbackResult] = {}
        self._started = False
        self._subscriber_id = _text("subscriber_id", subscriber_id)
        self._configure()

    @property
    def event_publisher(self) -> EventPublisher | None:
        with self._lock:
            return self._event_publisher

    @property
    def propagation_context(self) -> EventPropagationContext | None:
        with self._lock:
            return self._last_context

    @property
    def started(self) -> bool:
        with self._lock:
            return self._started

    def set_event_publisher(self, publisher: EventPublisher | None) -> None:
        if publisher is not None and not isinstance(publisher, EventPublisher):
            raise TypeError("publisher must be EventPublisher or None")
        with self._lock:
            self._event_publisher = publisher
        self._configure()

    def get(self, request_id: str) -> CognitiveFeedbackResult | None:
        _text("request_id", request_id)
        with self._lock:
            return self._results.get(request_id)

    def records(self) -> tuple[CognitiveFeedbackResult, ...]:
        with self._lock:
            return tuple(self._results[key] for key in sorted(self._results))

    def record(
        self,
        feedback: CognitiveFeedback,
        *,
        context: EventPropagationContext,
        created_at: datetime | None = None,
    ) -> CognitiveFeedbackResult:
        request = CognitiveFeedbackRequest.from_feedback(feedback, context=context, created_at=created_at)
        with self._lock:
            existing = self._results.get(request.request_id)
            publisher = self._event_publisher
            event_bus = self._event_bus
        if existing is not None:
            return existing
        if publisher is None or event_bus is None:
            return self._execute(request, context)
        with self._lock:
            self._pending_requests.add(request.request_id)
        try:
            request_context = self._publish(
                "CognitiveFeedbackRequested",
                EventType.START,
                {"request": request.to_dict()},
                context,
            )
            return self._execute(request, request_context)
        finally:
            with self._lock:
                self._pending_requests.discard(request.request_id)

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
            with self._lock:
                self._started = False
            return
        event_bus.subscribe(
            EventSubscription(
                subscriber_id=self._subscriber_id,
                handler=self._handle_request,
                event_name="CognitiveFeedbackRequested",
                priority=100,
            ),
            replace=True,
        )
        with self._lock:
            self._started = True

    def _handle_request(self, event: Event) -> None:
        payload = event.payload.get("request")
        if not isinstance(payload, Mapping):
            return
        try:
            request = CognitiveFeedbackRequest.from_dict(payload)
            with self._lock:
                if request.request_id in self._pending_requests:
                    return
            self._execute(request, EventPropagationContext.from_event(event))
        except Exception as exc:
            error("Cognitive feedback boundary event handling failed", {"error": str(exc)})

    def _execute(self, request: CognitiveFeedbackRequest, context: EventPropagationContext) -> CognitiveFeedbackResult:
        with self._lock:
            existing = self._results.get(request.request_id)
            if existing is not None:
                return existing
        result_context = context
        try:
            stored = self.cognition.record_feedback(request.feedback)
            if stored != request.feedback:
                raise ValueError(f"feedback storage conflict: {request.feedback.feedback_id}")
            result = CognitiveFeedbackResult(
                request_id=request.request_id,
                feedback_id=request.feedback.feedback_id,
                success=True,
                created_at=request.created_at,
                correlation_id=context.correlation_id,
                causation_id=context.causation_id,
                trace_id=context.trace_id,
                tenant_id=context.tenant_id,
            )
            with self._lock:
                self._results[request.request_id] = result
            result_context = self._publish(
                "CognitiveFeedbackRecorded",
                EventType.CREATED,
                {"request": request.to_dict(), "feedback": request.feedback.to_dict(), "result": result.to_dict()},
                context,
            )
        except Exception as exc:
            result = CognitiveFeedbackResult(
                request_id=request.request_id,
                feedback_id=request.feedback.feedback_id,
                success=False,
                created_at=request.created_at,
                correlation_id=context.correlation_id,
                causation_id=context.causation_id,
                trace_id=context.trace_id,
                tenant_id=context.tenant_id,
                error=f"{type(exc).__name__}: {exc}",
            )
            with self._lock:
                self._results[request.request_id] = result
            result_context = self._publish(
                "CognitiveFeedbackRejected",
                EventType.FAILURE,
                {"request": request.to_dict(), "result": result.to_dict()},
                context,
            )
        with self._lock:
            self._last_context = result_context
        return result

    def _publish(
        self,
        event_name: str,
        event_type: EventType,
        payload: Mapping[str, Any],
        context: EventPropagationContext,
    ) -> EventPropagationContext:
        publisher = self._event_publisher
        if publisher is None:
            return context
        try:
            event = Event.create(
                event_name=event_name,
                producer=self._subscriber_id,
                payload=payload,
                category=Category.LEARNING,
                event_type=event_type,
                correlation_id=context.correlation_id,
                causation_id=context.causation_id,
                trace_id=context.trace_id,
                tenant_id=context.tenant_id,
            )
            publisher.publish(event)
            return context.next(event.metadata.event_id)
        except Exception as exc:
            error("Cognitive feedback boundary event publication failed", {"event_name": event_name, "error": str(exc)})
            return context
