from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from threading import Condition, RLock
from types import MappingProxyType
from typing import Any, Protocol

from cognition.contracts import CognitiveResult
from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.utils.hash import short_id
from foundation.utils.logging import error
from infrastructure.event_bus import EventBus, EventPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext

__all__ = [
    "CognitiveLearningBoundary",
    "CognitiveLearningRequest",
    "CognitiveLearningResult",
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


def _matches_trace(
    candidate: object,
    requested: EventPropagationContext,
) -> bool:
    return (
        isinstance(candidate, EventPropagationContext)
        and candidate.correlation_id == requested.correlation_id
        and (
            requested.trace_id is None or candidate.trace_id == requested.trace_id
        )
        and (
            requested.tenant_id is None or candidate.tenant_id == requested.tenant_id
        )
    )


class LearningBackend(Protocol):
    def run(
        self,
        execution_result: dict[str, Any],
        *,
        context: EventPropagationContext | None = None,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class CognitiveLearningRequest:
    request_id: str
    result_id: str
    goal_id: str
    learning_input: Mapping[str, Any]
    created_at: datetime
    correlation_id: str
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _text("request_id", self.request_id)
        _text("result_id", self.result_id)
        _text("goal_id", self.goal_id)
        _text("correlation_id", self.correlation_id)
        object.__setattr__(self, "created_at", _timestamp(self.created_at))
        _optional_text("causation_id", self.causation_id)
        _optional_text("trace_id", self.trace_id)
        _optional_text("tenant_id", self.tenant_id)
        object.__setattr__(self, "learning_input", _mapping(self.learning_input))
        object.__setattr__(self, "metadata", _mapping(self.metadata))

    @classmethod
    def from_result(
        cls,
        result: CognitiveResult,
        *,
        context: EventPropagationContext,
        created_at: datetime | None = None,
    ) -> CognitiveLearningRequest:
        if not isinstance(result, CognitiveResult):
            raise TypeError("result must be CognitiveResult")
        if not isinstance(context, EventPropagationContext):
            raise TypeError("context must be EventPropagationContext")
        output = result.output if isinstance(result.output, Mapping) else {}
        goal = output.get("goal")
        plan = output.get("plan")
        decision = output.get("decision")
        goal_value = goal.get("intent") if isinstance(goal, Mapping) else result.goal_id
        steps = plan.get("steps", ()) if isinstance(plan, Mapping) else ()
        decision_value = decision.get("selected_option") if isinstance(decision, Mapping) else None
        learning_input = {
            "goal": goal_value,
            "plan": {"tree": {"children": list(steps) if isinstance(steps, (tuple, list)) else []}},
            "decision": decision_value,
            "result_id": result.result_id,
            "success": result.status.value == "success",
        }
        request_id = short_id(
            {
                "result_id": result.result_id,
                "goal_id": result.goal_id,
                "correlation_id": context.correlation_id,
                "causation_id": context.causation_id,
                "trace_id": context.trace_id,
                "tenant_id": context.tenant_id,
            },
            prefix="cognitive-learning:",
        )
        return cls(
            request_id=request_id,
            result_id=result.result_id,
            goal_id=result.goal_id,
            learning_input=learning_input,
            created_at=created_at or result.created_at,
            correlation_id=context.correlation_id,
            causation_id=context.causation_id,
            trace_id=context.trace_id,
            tenant_id=context.tenant_id,
            metadata={"result_status": result.status.value},
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CognitiveLearningRequest:
        if not isinstance(data, Mapping):
            raise TypeError("data must be a mapping")
        created_at = data.get("created_at")
        timestamp = created_at if isinstance(created_at, datetime) else datetime.fromisoformat(str(created_at))
        learning_input = data.get("learning_input")
        raw_metadata = data.get("metadata")
        metadata: Mapping[str, Any] = raw_metadata if isinstance(raw_metadata, Mapping) else {}
        return cls(
            request_id=_text("request_id", data.get("request_id")),
            result_id=_text("result_id", data.get("result_id")),
            goal_id=_text("goal_id", data.get("goal_id")),
            learning_input=learning_input if isinstance(learning_input, Mapping) else {},
            created_at=timestamp,
            correlation_id=_text("correlation_id", data.get("correlation_id")),
            causation_id=data.get("causation_id"),
            trace_id=data.get("trace_id"),
            tenant_id=data.get("tenant_id"),
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "result_id": self.result_id,
            "goal_id": self.goal_id,
            "learning_input": dict(self.learning_input),
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class CognitiveLearningResult:
    request_id: str
    result_id: str
    loop_id: str
    success: bool
    learning: Mapping[str, Any]
    created_at: datetime
    correlation_id: str
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    error: str | None = None
    _next_context: EventPropagationContext | None = field(
        default=None, compare=False, repr=False
    )

    def __post_init__(self) -> None:
        _text("request_id", self.request_id)
        _text("result_id", self.result_id)
        _text("loop_id", self.loop_id)
        if self._next_context is not None and not isinstance(
            self._next_context, EventPropagationContext
        ):
            raise TypeError("_next_context must be EventPropagationContext or None")
        _text("correlation_id", self.correlation_id)
        if not isinstance(self.success, bool):
            raise TypeError("success must be bool")
        object.__setattr__(self, "created_at", _timestamp(self.created_at))
        _optional_text("causation_id", self.causation_id)
        _optional_text("trace_id", self.trace_id)
        _optional_text("tenant_id", self.tenant_id)
        _optional_text("error", self.error)
        object.__setattr__(self, "learning", _mapping(self.learning))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CognitiveLearningResult:
        if not isinstance(data, Mapping):
            raise TypeError("data must be a mapping")
        created_at = data.get("created_at")
        timestamp = created_at if isinstance(created_at, datetime) else datetime.fromisoformat(str(created_at))
        success = data.get("success")
        if not isinstance(success, bool):
            raise TypeError("success must be bool")
        learning = data.get("learning")
        return cls(
            request_id=_text("request_id", data.get("request_id")),
            result_id=_text("result_id", data.get("result_id")),
            loop_id=_text("loop_id", data.get("loop_id")),
            success=success,
            learning=learning if isinstance(learning, Mapping) else {},
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
            "result_id": self.result_id,
            "loop_id": self.loop_id,
            "success": self.success,
            "learning": dict(self.learning),
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "error": self.error,
        }

    @property
    def propagation_context(self) -> EventPropagationContext:
        if self._next_context is not None:
            return self._next_context
        return EventPropagationContext.create(
            correlation_id=self.correlation_id,
            causation_id=self.causation_id,
            trace_id=self.trace_id,
            tenant_id=self.tenant_id,
        )


class CognitiveLearningBoundary:
    __slots__ = (
        "_backend_lock",
        "_condition",
        "_event_bus",
        "_event_publisher",
        "_last_context",
        "_pending",
        "_results",
        "_started",
        "_subscriber_id",
        "learning",
    )

    def __init__(
        self,
        learning: LearningBackend,
        event_publisher: EventPublisher | None = None,
        *,
        subscriber_id: str = "cognition.learning-boundary",
    ) -> None:
        if learning is None or not callable(getattr(learning, "run", None)):
            raise TypeError("learning must provide run")
        if event_publisher is not None and not isinstance(event_publisher, EventPublisher):
            raise TypeError("event_publisher must be EventPublisher or None")
        self.learning = learning
        self._backend_lock = RLock()
        self._event_publisher = event_publisher
        self._event_bus: EventBus | None = None
        self._condition = Condition(RLock())
        self._last_context: EventPropagationContext | None = None
        self._pending: set[str] = set()
        self._results: dict[str, CognitiveLearningResult] = {}
        self._started = False
        self._subscriber_id = _text("subscriber_id", subscriber_id)
        self._configure()

    @property
    def event_publisher(self) -> EventPublisher | None:
        with self._condition:
            return self._event_publisher

    @property
    def propagation_context(self) -> EventPropagationContext | None:
        with self._condition:
            return self._last_context

    @property
    def started(self) -> bool:
        with self._condition:
            return self._started

    def set_event_publisher(self, publisher: EventPublisher | None) -> None:
        if publisher is not None and not isinstance(publisher, EventPublisher):
            raise TypeError("publisher must be EventPublisher or None")
        with self._condition:
            self._event_publisher = publisher
        self._configure()

    def get(self, request_id: str) -> CognitiveLearningResult | None:
        _text("request_id", request_id)
        with self._condition:
            return self._results.get(request_id)

    def records(self) -> tuple[CognitiveLearningResult, ...]:
        with self._condition:
            return tuple(self._results[key] for key in sorted(self._results))

    def record(
        self,
        result: CognitiveResult,
        *,
        context: EventPropagationContext,
        created_at: datetime | None = None,
    ) -> CognitiveLearningResult:
        request = CognitiveLearningRequest.from_result(result, context=context, created_at=created_at)
        owner = False
        with self._condition:
            existing = self._results.get(request.request_id)
            if existing is not None:
                return existing
            while request.request_id in self._pending:
                self._condition.wait_for(lambda: request.request_id in self._results or request.request_id not in self._pending)
                existing = self._results.get(request.request_id)
                if existing is not None:
                    return existing
            self._pending.add(request.request_id)
            owner = True
            publisher = self._event_publisher
            event_bus = self._event_bus
        if not owner:
            raise RuntimeError(f"learning request ownership lost: {request.request_id}")
        try:
            if publisher is None or event_bus is None:
                return self._execute(request, context)
            request_context = self._publish(
                "CognitiveLearningRequested",
                EventType.START,
                {"request": request.to_dict()},
                context,
            )
            result_value = self._execute(request, request_context)
            return result_value
        finally:
            with self._condition:
                self._pending.remove(request.request_id)
                self._condition.notify_all()

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
            with self._condition:
                self._started = False
            return
        event_bus.subscribe(
            EventSubscription(
                subscriber_id=self._subscriber_id,
                handler=self._handle_request,
                event_name="CognitiveLearningRequested",
                priority=100,
            ),
            replace=True,
        )
        with self._condition:
            self._started = True

    def _handle_request(self, event: Event) -> None:
        payload = event.payload.get("request")
        if not isinstance(payload, Mapping):
            return
        try:
            request = CognitiveLearningRequest.from_dict(payload)
            with self._condition:
                pending = self._pending
                if request.request_id in pending:
                    return
            self._execute(request, EventPropagationContext.from_event(event))
        except Exception as exc:
            error("Cognitive learning boundary event handling failed", {"error": str(exc)})

    def _execute(
        self,
        request: CognitiveLearningRequest,
        context: EventPropagationContext,
    ) -> CognitiveLearningResult:
        with self._condition:
            existing = self._results.get(request.request_id)
            if existing is not None:
                return existing
        result_context = context
        try:
            with self._backend_lock:
                backend_context_before = getattr(self.learning, "propagation_context", None)
                try:
                    learning = self.learning.run(dict(request.learning_input), context=context)
                finally:
                    backend_context_after = getattr(self.learning, "propagation_context", None)
                    if (
                        isinstance(backend_context_after, EventPropagationContext)
                        and _matches_trace(backend_context_after, context)
                        and backend_context_after != backend_context_before
                    ):
                        result_context = backend_context_after
            if not isinstance(learning, Mapping):
                raise TypeError("learning backend result must be a mapping")
            loop_id = learning.get("loop_id")
            if not isinstance(loop_id, str) or not loop_id.strip():
                loop_id = "learning"
            result = CognitiveLearningResult(
                request_id=request.request_id,
                result_id=request.result_id,
                loop_id=loop_id,
                success=True,
                learning=learning,
                created_at=request.created_at,
                correlation_id=result_context.correlation_id,
                causation_id=result_context.causation_id,
                trace_id=result_context.trace_id,
                tenant_id=result_context.tenant_id,
            )
        except Exception as exc:
            result = CognitiveLearningResult(
                request_id=request.request_id,
                result_id=request.result_id,
                loop_id="learning",
                success=False,
                learning={},
                created_at=request.created_at,
                correlation_id=result_context.correlation_id,
                causation_id=result_context.causation_id,
                trace_id=result_context.trace_id,
                tenant_id=result_context.tenant_id,
                error=f"{type(exc).__name__}: {exc}",
            )
        with self._condition:
            self._results[request.request_id] = result
        event_name = "CognitiveLearningCompleted" if result.success else "CognitiveLearningFailed"
        event_type = EventType.COMPLETE if result.success else EventType.FAILURE
        final_context = self._publish(
            event_name,
            event_type,
            {"request": request.to_dict(), "result": result.to_dict()},
            result_context,
        )
        result = replace(result, _next_context=final_context)

        with self._condition:
            self._results[request.request_id] = result
            self._last_context = final_context
            self._condition.notify_all()

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
            error("Cognitive learning boundary event publication failed", {"event_name": event_name, "error": str(exc)})
            return context
