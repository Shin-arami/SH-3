from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Event as ThreadEvent
from threading import RLock
from types import MappingProxyType
from typing import Any, Protocol

from cognition.contracts import CognitiveResult
from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.utils.hash import short_id
from foundation.utils.logging import error
from infrastructure.event_bus import EventBus, EventPublisher
from infrastructure.events import Event, EventPropagationContext
from kernel.learning_feedback_loop import ClosedLoopStatus, LearningClosedLoopReport

__all__ = ["CognitiveClosedLoopBoundary", "CognitiveClosedLoopRequest", "CognitiveClosedLoopResult"]


class ClosedLoopBackend(Protocol):
    def run(
        self,
        result: CognitiveResult,
        *,
        context: EventPropagationContext | None = None,
        optimize: bool = True,
        recover: bool = True,
    ) -> LearningClosedLoopReport: ...


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


@dataclass(frozen=True, slots=True)
class CognitiveClosedLoopRequest:
    request_id: str
    result: CognitiveResult
    created_at: datetime
    correlation_id: str
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    optimize: bool = True
    recover: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _text("request_id", self.request_id)
        if not isinstance(self.result, CognitiveResult):
            raise TypeError("result must be CognitiveResult")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        _text("correlation_id", self.correlation_id)
        for field_name, field_value in (
            ("causation_id", self.causation_id),
            ("trace_id", self.trace_id),
            ("tenant_id", self.tenant_id),
        ):
            if field_value is not None:
                _text(field_name, field_value)
        if not isinstance(self.optimize, bool):
            raise TypeError("optimize must be bool")
        if not isinstance(self.recover, bool):
            raise TypeError("recover must be bool")
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))
        object.__setattr__(self, "metadata", _mapping(self.metadata))

    @classmethod
    def from_result(
        cls,
        result: CognitiveResult,
        *,
        context: EventPropagationContext,
        optimize: bool = True,
        recover: bool = True,
        created_at: datetime | None = None,
    ) -> CognitiveClosedLoopRequest:
        if not isinstance(result, CognitiveResult):
            raise TypeError("result must be CognitiveResult")
        if not isinstance(context, EventPropagationContext):
            raise TypeError("context must be EventPropagationContext")
        request_id = short_id(
            {
                "result_id": result.result_id,
                "optimize": optimize,
                "recover": recover,
            },
            prefix="cognitive-closed-loop:",
        )
        return cls(
            request_id=request_id,
            result=result,
            created_at=created_at or result.created_at,
            correlation_id=context.correlation_id,
            causation_id=context.causation_id,
            trace_id=context.trace_id,
            tenant_id=context.tenant_id,
            optimize=optimize,
            recover=recover,
            metadata={"result_id": result.result_id},
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CognitiveClosedLoopRequest:
        if not isinstance(data, Mapping):
            raise TypeError("data must be a mapping")
        result_data = data.get("result")
        if not isinstance(result_data, Mapping):
            raise TypeError("result must be a mapping")
        from kernel.learning_feedback_loop import LearningClosedLoopCoordinator
        result = LearningClosedLoopCoordinator._result_from_dict(result_data)
        if result is None:
            raise ValueError("result must be a valid CognitiveResult")
        created_at = data.get("created_at")
        timestamp = created_at if isinstance(created_at, datetime) else datetime.fromisoformat(str(created_at))
        return cls(
            request_id=_text("request_id", data.get("request_id")),
            result=result,
            created_at=timestamp,
            correlation_id=_text("correlation_id", data.get("correlation_id")),
            causation_id=data.get("causation_id"),
            trace_id=data.get("trace_id"),
            tenant_id=data.get("tenant_id"),
            optimize=data.get("optimize", True),
            recover=data.get("recover", True),
            metadata=data.get("metadata", {}) if isinstance(data.get("metadata", {}), Mapping) else {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "result": self.result.to_dict(),
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "optimize": self.optimize,
            "recover": self.recover,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class CognitiveClosedLoopResult:
    request_id: str
    cycle_id: str
    success: bool
    report: LearningClosedLoopReport | None
    created_at: datetime
    correlation_id: str
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        _text("request_id", self.request_id)
        _text("cycle_id", self.cycle_id)
        if not isinstance(self.success, bool):
            raise TypeError("success must be bool")
        if self.report is not None and not isinstance(self.report, LearningClosedLoopReport):
            raise TypeError("report must be LearningClosedLoopReport or None")
        if self.success != (self.report is not None and self.report.status is not ClosedLoopStatus.FAILED):
            raise ValueError("success must match report status")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        _text("correlation_id", self.correlation_id)
        for field_name, field_value in (
            ("causation_id", self.causation_id),
            ("trace_id", self.trace_id),
            ("tenant_id", self.tenant_id),
        ):
            if field_value is not None:
                _text(field_name, field_value)
        if self.error is not None:
            _text("error", self.error)
        if self.success and self.error is not None:
            raise ValueError("successful result must not contain error")
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "cycle_id": self.cycle_id,
            "success": self.success,
            "report": None if self.report is None else self.report.to_dict(),
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "error": self.error,
        }


class CognitiveClosedLoopBoundary:
    __slots__ = (
        "_event_bus",
        "_event_publisher",
        "_inflight",
        "_last_context",
        "_lock",
        "_results",
        "_subscriber_id",
        "backend",
    )

    def __init__(
        self,
        backend: ClosedLoopBackend,
        event_publisher: EventPublisher | None = None,
        *,
        subscriber_id: str = "cognition.closed-loop-boundary",
    ) -> None:
        if backend is None or not callable(getattr(backend, "run", None)):
            raise TypeError("backend must provide run")
        if event_publisher is not None and not isinstance(event_publisher, EventPublisher):
            raise TypeError("event_publisher must be EventPublisher or None")
        self.backend = backend
        self._event_publisher = event_publisher
        self._event_bus: EventBus | None = None
        self._last_context: EventPropagationContext | None = None
        self._lock = RLock()
        self._inflight: dict[str, ThreadEvent] = {}
        self._results: dict[str, CognitiveClosedLoopResult] = {}
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

    def records(self) -> tuple[CognitiveClosedLoopResult, ...]:
        with self._lock:
            return tuple(self._results[key] for key in sorted(self._results))

    def get(self, request_id: str) -> CognitiveClosedLoopResult | None:
        _text("request_id", request_id)
        with self._lock:
            return self._results.get(request_id)

    def set_event_publisher(self, publisher: EventPublisher | None) -> None:
        if publisher is not None and not isinstance(publisher, EventPublisher):
            raise TypeError("publisher must be EventPublisher or None")
        with self._lock:
            self._event_publisher = publisher
        self._configure()

    def request(
        self,
        result: CognitiveResult,
        *,
        context: EventPropagationContext,
        optimize: bool = True,
        recover: bool = True,
        created_at: datetime | None = None,
    ) -> CognitiveClosedLoopResult:
        request = CognitiveClosedLoopRequest.from_result(
            result,
            context=context,
            optimize=optimize,
            recover=recover,
            created_at=created_at,
        )
        with self._lock:
            existing = self._results.get(request.request_id)
            if existing is not None:
                return existing
            waiter = self._inflight.get(request.request_id)
            if waiter is None:
                waiter = ThreadEvent()
                self._inflight[request.request_id] = waiter
                leader = True
            else:
                leader = False
        if not leader:
            waiter.wait()
            resolved = self.get(request.request_id)
            if resolved is None:
                raise RuntimeError(f"closed loop result not produced: {request.request_id}")
            return resolved
        try:
            propagation = self._publish(
                "CognitiveClosedLoopRequested",
                EventType.START,
                {"request": request.to_dict()},
                context,
            )
            try:
                report = self.backend.run(
                    request.result,
                    context=propagation,
                    optimize=request.optimize,
                    recover=request.recover,
                )
                success = report.status is not ClosedLoopStatus.FAILED
                outcome = CognitiveClosedLoopResult(
                    request_id=request.request_id,
                    cycle_id=report.cycle_id,
                    success=success,
                    report=report,
                    created_at=request.created_at,
                    correlation_id=propagation.correlation_id,
                    causation_id=propagation.causation_id,
                    trace_id=propagation.trace_id,
                    tenant_id=propagation.tenant_id,
                )
                with self._lock:
                    self._results[request.request_id] = outcome
                    self._last_context = propagation
                terminal_name = "CognitiveClosedLoopCompleted" if success else "CognitiveClosedLoopFailed"
                terminal_type = EventType.COMPLETE if success else EventType.FAILURE
                self._last_context = self._publish(terminal_name, terminal_type, {"request": request.to_dict(), "result": outcome.to_dict()}, propagation)
                return outcome
            except Exception as exc:
                outcome = CognitiveClosedLoopResult(
                    request_id=request.request_id,
                    cycle_id=f"learning-cycle:{request.result.result_id}",
                    success=False,
                    report=None,
                    created_at=request.created_at,
                    correlation_id=propagation.correlation_id,
                    causation_id=propagation.causation_id,
                    trace_id=propagation.trace_id,
                    tenant_id=propagation.tenant_id,
                    error=f"{type(exc).__name__}: {exc}",
                )
                with self._lock:
                    self._results[request.request_id] = outcome
                    self._last_context = propagation
                self._last_context = self._publish(
                    "CognitiveClosedLoopFailed",
                    EventType.FAILURE,
                    {"request": request.to_dict(), "result": outcome.to_dict()},
                    propagation,
                )
                return outcome
        finally:
            with self._lock:
                waiter = self._inflight.pop(request.request_id, None)
                if waiter is not None:
                    waiter.set()

    def _configure(self) -> None:
        publisher = self._event_publisher
        event_bus = getattr(publisher, "event_bus", None) if publisher is not None else None
        if event_bus is not None and not isinstance(event_bus, EventBus):
            event_bus = None
        with self._lock:
            self._event_bus = event_bus

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
            error("Cognitive closed loop event publication failed", {"event_name": event_name, "error": str(exc)})
            return context
