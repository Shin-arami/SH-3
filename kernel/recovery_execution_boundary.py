from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Event as ThreadEvent
from threading import RLock
from types import MappingProxyType
from typing import Any, Protocol

from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.utils.hash import short_id
from foundation.utils.logging import error
from infrastructure.event_bus import EventBus, EventPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from kernel.recovery_strategy_boundary import RecoveryStrategyResult
from self_healing.core import FailureSnapshot

__all__ = [
    "RecoveryExecutionBoundary",
    "RecoveryExecutionRequest",
    "RecoveryExecutionResult",
]


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


class RecoveryExecutionBackend(Protocol):
    def recover_with_strategy(self, snapshot: FailureSnapshot, strategy: str) -> Any: ...


@dataclass(frozen=True, slots=True)
class RecoveryExecutionRequest:
    request_id: str
    strategy_request_id: str
    failure_id: str
    strategy: str
    created_at: datetime
    correlation_id: str
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name, field_value in (
            ("request_id", self.request_id),
            ("strategy_request_id", self.strategy_request_id),
            ("failure_id", self.failure_id),
            ("strategy", self.strategy),
            ("correlation_id", self.correlation_id),
        ):
            _text(field_name, field_value)
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        for optional_name, optional_value in (
            ("causation_id", self.causation_id),
            ("trace_id", self.trace_id),
            ("tenant_id", self.tenant_id),
        ):
            if optional_value is not None:
                _text(optional_name, optional_value)
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))
        object.__setattr__(self, "metadata", _mapping(self.metadata))

    @classmethod
    def from_strategy(
        cls,
        result: RecoveryStrategyResult,
        *,
        snapshot: FailureSnapshot,
        context: EventPropagationContext,
        created_at: datetime | None = None,
    ) -> RecoveryExecutionRequest:
        if not isinstance(result, RecoveryStrategyResult):
            raise TypeError("result must be RecoveryStrategyResult")
        if not isinstance(snapshot, FailureSnapshot):
            raise TypeError("snapshot must be FailureSnapshot")
        if result.failure_id != snapshot.trace_id:
            raise ValueError("strategy result failure_id does not match snapshot")
        if not isinstance(context, EventPropagationContext):
            raise TypeError("context must be EventPropagationContext")
        request_id = short_id(
            {
                "strategy_request_id": result.request_id,
                "failure_id": result.failure_id,
                "strategy": result.selected_strategy,
            },
            prefix="recovery-execution:",
        )
        return cls(
            request_id=request_id,
            strategy_request_id=result.request_id,
            failure_id=result.failure_id,
            strategy=result.selected_strategy,
            created_at=created_at or result.created_at,
            correlation_id=context.correlation_id,
            causation_id=context.causation_id,
            trace_id=context.trace_id,
            tenant_id=context.tenant_id,
            metadata={"strategy_confidence": result.confidence, "learned": result.learned},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "strategy_request_id": self.strategy_request_id,
            "failure_id": self.failure_id,
            "strategy": self.strategy,
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class RecoveryExecutionResult:
    request_id: str
    strategy_request_id: str
    failure_id: str
    strategy: str
    success: bool
    result: Any
    created_at: datetime
    correlation_id: str
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        for field_name, field_value in (
            ("request_id", self.request_id),
            ("strategy_request_id", self.strategy_request_id),
            ("failure_id", self.failure_id),
            ("strategy", self.strategy),
            ("correlation_id", self.correlation_id),
        ):
            _text(field_name, field_value)
        if not isinstance(self.success, bool):
            raise TypeError("success must be bool")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        for optional_name, optional_value in (
            ("causation_id", self.causation_id),
            ("trace_id", self.trace_id),
            ("tenant_id", self.tenant_id),
            ("error", self.error),
        ):
            if optional_value is not None:
                _text(optional_name, optional_value)
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))

    @property
    def propagation_context(self) -> EventPropagationContext:
        return EventPropagationContext.create(
            correlation_id=self.correlation_id,
            causation_id=self.causation_id,
            trace_id=self.trace_id,
            tenant_id=self.tenant_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "strategy_request_id": self.strategy_request_id,
            "failure_id": self.failure_id,
            "strategy": self.strategy,
            "success": self.success,
            "result": self.result,
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "error": self.error,
        }


class RecoveryExecutionBoundary:
    __slots__ = (
        "_event_bus",
        "_event_publisher",
        "_inflight",
        "_last_context",
        "_lock",
        "_pending",
        "_results",
        "_subscriber_id",
        "backend",
    )

    def __init__(
        self,
        backend: RecoveryExecutionBackend,
        event_publisher: EventPublisher | None = None,
        *,
        subscriber_id: str = "recovery.execution-boundary",
    ) -> None:
        if backend is None:
            raise TypeError("backend must not be None")
        if not callable(getattr(backend, "recover_with_strategy", None)):
            raise TypeError("backend must provide recover_with_strategy")
        if event_publisher is not None and not isinstance(event_publisher, EventPublisher):
            raise TypeError("event_publisher must be EventPublisher or None")
        self.backend = backend
        self._event_publisher = event_publisher
        self._event_bus: EventBus | None = None
        self._lock = RLock()
        self._results: dict[str, RecoveryExecutionResult] = {}
        self._pending: dict[str, tuple[RecoveryExecutionRequest, FailureSnapshot]] = {}
        self._inflight: dict[str, ThreadEvent] = {}
        self._last_context: EventPropagationContext | None = None
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

    def set_event_publisher(self, publisher: EventPublisher | None) -> None:
        if publisher is not None and not isinstance(publisher, EventPublisher):
            raise TypeError("publisher must be EventPublisher or None")
        with self._lock:
            self._event_publisher = publisher
        self._configure()

    def records(self) -> tuple[RecoveryExecutionResult, ...]:
        with self._lock:
            return tuple(self._results[key] for key in sorted(self._results))

    def get(self, request_id: str) -> RecoveryExecutionResult | None:
        _text("request_id", request_id)
        with self._lock:
            return self._results.get(request_id)

    def request(
        self,
        strategy_result: RecoveryStrategyResult,
        snapshot: FailureSnapshot,
        *,
        context: EventPropagationContext,
        created_at: datetime | None = None,
    ) -> RecoveryExecutionResult:
        request = RecoveryExecutionRequest.from_strategy(
            strategy_result,
            snapshot=snapshot,
            context=context,
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
                self._pending[request.request_id] = (request, snapshot)
                leader = True
            else:
                leader = False
        if not leader:
            waiter.wait()
            result = self.get(request.request_id)
            if result is None:
                raise RuntimeError(f"recovery execution result not produced: {request.request_id}")
            return result
        try:
            publisher = self.event_publisher
            event_bus = self._event_bus
            if publisher is None or event_bus is None:
                return self._execute(request, snapshot, context=context)
            self._publish(
                "RecoveryExecutionRequested",
                EventType.START,
                {"request_id": request.request_id, "failure_id": request.failure_id, "strategy": request.strategy},
                context,
            )
            result = self.get(request.request_id)
            if result is None:
                raise RuntimeError(f"recovery execution result not produced: {request.request_id}")
            return result
        finally:
            with self._lock:
                waiter = self._inflight.pop(request.request_id, None)
                self._pending.pop(request.request_id, None)
                if waiter is not None:
                    waiter.set()

    def _configure(self) -> None:
        publisher = self.event_publisher
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
                handler=self._handle_request,
                event_name="RecoveryExecutionRequested",
                priority=100,
            ),
            replace=True,
        )

    def _handle_request(self, event: Event) -> None:
        request_id = event.payload.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            return
        with self._lock:
            pending = self._pending.get(request_id)
        if pending is None:
            return
        request, snapshot = pending
        context = EventPropagationContext.from_event(event)
        try:
            self._execute(request, snapshot, context=context)
        except Exception as exc:
            self._publish(
                "RecoveryExecutionFailed",
                EventType.FAILURE,
                {"request_id": request.request_id, "failure_id": request.failure_id, "strategy": request.strategy, "error": str(exc)},
                context,
            )
            error("Recovery execution boundary event handling failed", {"error": str(exc), "request_id": request.request_id})

    def _execute(
        self,
        request: RecoveryExecutionRequest,
        snapshot: FailureSnapshot,
        *,
        context: EventPropagationContext,
    ) -> RecoveryExecutionResult:
        with self._lock:
            existing = self._results.get(request.request_id)
        if existing is not None:
            return existing
        setter = getattr(self.backend, "set_propagation_context", None)
        if callable(setter):
            setter(context)
        success = False
        value: Any = None
        error_message: str | None = None
        try:
            value = self.backend.recover_with_strategy(snapshot, request.strategy)
            success = True
        except Exception as exc:
            error_message = str(exc)
        final_context = self._publish(
            "RecoveryExecutionCompleted" if success else "RecoveryExecutionFailed",
            EventType.COMPLETE if success else EventType.FAILURE,
            {
                "request_id": request.request_id,
                "failure_id": request.failure_id,
                "strategy": request.strategy,
                "success": success,
                **({"result": value} if success else {"error": error_message or "recovery execution failed"}),
            },
            context,
        )
        result = RecoveryExecutionResult(
            request_id=request.request_id,
            strategy_request_id=request.strategy_request_id,
            failure_id=request.failure_id,
            strategy=request.strategy,
            success=success,
            result=value,
            created_at=request.created_at,
            correlation_id=final_context.correlation_id,
            causation_id=final_context.causation_id,
            trace_id=final_context.trace_id,
            tenant_id=final_context.tenant_id,
            error=error_message,
        )
        with self._lock:
            self._last_context = final_context
            self._results[request.request_id] = result
        return result

    def _publish(
        self,
        event_name: str,
        event_type: EventType,
        payload: Mapping[str, Any],
        context: EventPropagationContext,
    ) -> EventPropagationContext:
        publisher = self.event_publisher
        if publisher is None:
            return context
        try:
            event = Event.create(
                event_name=event_name,
                producer=self._subscriber_id,
                payload=payload,
                category=Category.ACTION,
                event_type=event_type,
                correlation_id=context.correlation_id,
                causation_id=context.causation_id,
                trace_id=context.trace_id,
                tenant_id=context.tenant_id,
            )
            publisher.publish(event)
            return context.next(event.metadata.event_id)
        except Exception as exc:
            error("Recovery execution event publication failed", {"event_name": event_name, "error": str(exc)})
            return context
