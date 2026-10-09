from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import isfinite
from threading import RLock
from types import MappingProxyType
from typing import Any, Protocol

from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.utils.hash import short_id
from foundation.utils.logging import error
from infrastructure.event_bus import EventBus, EventPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from kernel.optimizer_update_boundary import OptimizationUpdateBoundary

__all__ = [
    "LEARNING_RESULT_DOMAIN",
    "LearningOptimizationRequest",
    "LearningOptimizationResult",
    "LearningOptimizerBoundary",
]


LEARNING_RESULT_DOMAIN = "cognition.result"


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


class OptimizerBackend(Protocol):
    def optimize(
        self,
        *,
        context: EventPropagationContext | None = None,
        execute: bool = False,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class LearningOptimizationRequest:
    request_id: str
    learning_record_id: str
    domain: str
    success: bool
    score: float
    strategy: str | None
    created_at: datetime
    correlation_id: str
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in (
            ("request_id", self.request_id),
            ("learning_record_id", self.learning_record_id),
            ("domain", self.domain),
            ("correlation_id", self.correlation_id),
        ):
            _text(name, value)
        if not isinstance(self.success, bool):
            raise TypeError("success must be bool")
        if not isinstance(self.score, (int, float)) or isinstance(self.score, bool):
            raise TypeError("score must be numeric")
        if not isfinite(float(self.score)) or not 0.0 <= float(self.score) <= 1.0:
            raise ValueError("score must be finite and between 0.0 and 1.0")
        if self.strategy is not None:
            _text("strategy", self.strategy)
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        for optional_name, optional_value in (
            ("causation_id", self.causation_id),
            ("trace_id", self.trace_id),
            ("tenant_id", self.tenant_id),
        ):
            if optional_value is not None:
                _text(optional_name, optional_value)
        object.__setattr__(self, "score", float(self.score))
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))
        object.__setattr__(self, "metadata", _mapping(self.metadata))

    @classmethod
    def from_learning_result(
        cls,
        learning_result: Mapping[str, Any],
        *,
        context: EventPropagationContext,
        created_at: datetime | None = None,
    ) -> LearningOptimizationRequest:
        if not isinstance(learning_result, Mapping):
            raise TypeError("learning_result must be a mapping")
        record_id = learning_result.get("record_id")
        if not isinstance(record_id, str) or not record_id.strip():
            memory_key = learning_result.get("memory_key")
            record_id = memory_key if isinstance(memory_key, str) and memory_key.strip() else None
        if record_id is None:
            loop_id = learning_result.get("loop_id")
            record_id = loop_id if isinstance(loop_id, str) and loop_id.strip() else None
        if record_id is None:
            record_id = short_id(
                {
                    "domain": learning_result.get("domain"),
                    "success": learning_result.get("success"),
                    "score": learning_result.get("score"),
                    "details": learning_result.get("details", {}),
                },
                prefix="learning-record:",
            )
        domain = learning_result.get("domain")
        if not isinstance(domain, str) or not domain.strip():
            domain = LEARNING_RESULT_DOMAIN
        success = learning_result.get("success")
        score = learning_result.get("score")
        if success is None:
            success = True
        if not isinstance(success, bool):
            raise TypeError("learning_result.success must be bool")
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            raise TypeError("learning_result.score must be numeric")
        details = learning_result.get("details")
        strategy: str | None = None
        if isinstance(details, Mapping):
            value = details.get("strategy")
            if isinstance(value, str) and value.strip():
                strategy = value
        metadata = learning_result.get("metadata")
        request_id = short_id(
            {"learning_record_id": record_id, "domain": domain},
            prefix="learning-optimization:",
        )
        return cls(
            request_id=request_id,
            learning_record_id=record_id,
            domain=domain,
            success=success,
            score=float(score),
            strategy=strategy,
            created_at=created_at or datetime.now(UTC),
            correlation_id=context.correlation_id,
            causation_id=context.causation_id,
            trace_id=context.trace_id,
            tenant_id=context.tenant_id,
            metadata=metadata if isinstance(metadata, Mapping) else {},
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LearningOptimizationRequest:
        if not isinstance(data, Mapping):
            raise TypeError("data must be a mapping")
        created_at = data.get("created_at")
        timestamp = (
            created_at
            if isinstance(created_at, datetime)
            else datetime.fromisoformat(str(created_at))
        )
        metadata = data.get("metadata")
        success = data.get("success")
        if not isinstance(success, bool):
            raise TypeError("success must be bool")
        score = data.get("score")
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            raise TypeError("score must be numeric")
        strategy = data.get("strategy")
        if strategy is not None and not isinstance(strategy, str):
            raise TypeError("strategy must be str or None")
        return cls(
            request_id=_text("request_id", data.get("request_id")),
            learning_record_id=_text(
                "learning_record_id", data.get("learning_record_id")
            ),
            domain=_text("domain", data.get("domain")),
            success=success,
            score=float(score),
            strategy=strategy,
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
            "learning_record_id": self.learning_record_id,
            "domain": self.domain,
            "success": self.success,
            "score": self.score,
            "strategy": self.strategy,
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class LearningOptimizationResult:
    request_id: str
    learning_record_id: str
    optimizer_id: str
    success: bool
    optimization: Mapping[str, Any]
    created_at: datetime
    correlation_id: str
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("request_id", self.request_id),
            ("learning_record_id", self.learning_record_id),
            ("optimizer_id", self.optimizer_id),
            ("correlation_id", self.correlation_id),
        ):
            _text(name, value)
        if not isinstance(self.success, bool):
            raise TypeError("success must be bool")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        for optional_name, optional_value in (
            ("causation_id", self.causation_id),
            ("trace_id", self.trace_id),
            ("tenant_id", self.tenant_id),
        ):
            if optional_value is not None:
                _text(optional_name, optional_value)
        if self.error is not None:
            _text("error", self.error)
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))
        object.__setattr__(self, "optimization", _mapping(self.optimization))

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "learning_record_id": self.learning_record_id,
            "optimizer_id": self.optimizer_id,
            "success": self.success,
            "optimization": dict(self.optimization),
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "error": self.error,
        }


class LearningOptimizerBoundary:
    __slots__ = (
        "_event_bus",
        "_event_publisher",
        "_last_context",
        "_lock",
        "_results",
        "_started",
        "_subscriber_id",
        "_update_boundary",
        "optimizer",
    )

    def __init__(
        self,
        optimizer: OptimizerBackend,
        event_publisher: EventPublisher | None = None,
        *,
        subscriber_id: str = "learning.optimizer-boundary",
        update_boundary: OptimizationUpdateBoundary | None = None,
    ) -> None:
        if optimizer is None or not callable(getattr(optimizer, "optimize", None)):
            raise TypeError("optimizer must provide optimize")
        if event_publisher is not None and not isinstance(
            event_publisher, EventPublisher
        ):
            raise TypeError("event_publisher must be EventPublisher or None")
        self.optimizer = optimizer
        if update_boundary is not None and not isinstance(update_boundary, OptimizationUpdateBoundary):
            raise TypeError("update_boundary must be OptimizationUpdateBoundary or None")
        self._update_boundary = update_boundary
        self._event_publisher = event_publisher
        self._event_bus: EventBus | None = None
        self._lock = RLock()
        self._results: dict[str, LearningOptimizationResult] = {}
        self._last_context: EventPropagationContext | None = None
        self._started = False
        self._subscriber_id = _text("subscriber_id", subscriber_id)
        self._configure()

    @property
    def update_boundary(self) -> OptimizationUpdateBoundary | None:
        return self._update_boundary

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

    def records(self) -> tuple[LearningOptimizationResult, ...]:
        with self._lock:
            return tuple(self._results[key] for key in sorted(self._results))

    def get(self, request_id: str) -> LearningOptimizationResult | None:
        _text("request_id", request_id)
        with self._lock:
            return self._results.get(request_id)

    def request(
        self,
        learning_result: Mapping[str, Any],
        *,
        context: EventPropagationContext,
        created_at: datetime | None = None,
    ) -> LearningOptimizationResult:
        request = LearningOptimizationRequest.from_learning_result(
            learning_result,
            context=context,
            created_at=created_at,
        )
        with self._lock:
            existing = self._results.get(request.request_id)
            publisher = self._event_publisher
            event_bus = self._event_bus
        if existing is not None:
            return existing
        if publisher is None or event_bus is None:
            return self._execute(request, context)
        self._publish(
            "LearningOptimizationRequested",
            EventType.START,
            {"request": request.to_dict()},
            context,
        )
        result = self.get(request.request_id)
        if result is None:
            raise RuntimeError(
                f"optimization result not produced: {request.request_id}"
            )
        return result

    def _configure(self) -> None:
        publisher = self._event_publisher
        event_bus = (
            getattr(publisher, "event_bus", None)
            if publisher is not None
            else None
        )
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
                event_name="LearningOptimizationRequested",
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
            request = LearningOptimizationRequest.from_dict(payload)
            context = EventPropagationContext.from_event(event)
            self._execute(request, context)
        except Exception as exc:
            error(
                "Learning optimizer boundary event handling failed",
                {"error": str(exc)},
            )

    def _execute(
        self,
        request: LearningOptimizationRequest,
        context: EventPropagationContext,
    ) -> LearningOptimizationResult:
        with self._lock:
            existing = self._results.get(request.request_id)
            if existing is not None:
                return existing
            try:
                update_boundary = self._update_boundary
                if update_boundary is None:
                    optimization = self.optimizer.optimize(context=context, execute=True)
                    optimizer_id = str(optimization.get("optimizer_id", "optimizer"))
                    success = self._optimization_success(optimization)
                else:
                    optimization = self.optimizer.optimize(context=context, execute=False)
                    optimizer_id = str(optimization.get("optimizer_id", "optimizer"))
                    optimizer_context = getattr(self.optimizer, "propagation_context", None)
                    update_context = optimizer_context if isinstance(optimizer_context, EventPropagationContext) else context
                    update = update_boundary.request(optimization, context=update_context, created_at=request.created_at)
                    optimization = dict(optimization)
                    optimization["update"] = update.to_dict()
                    success = update.success
                error_message = None
            except Exception as exc:
                optimization = {}
                optimizer_id = str(getattr(self.optimizer, "optimizer_id", "optimizer"))
                success = False
                error_message = str(exc)
            result = LearningOptimizationResult(
                request_id=request.request_id,
                learning_record_id=request.learning_record_id,
                optimizer_id=optimizer_id,
                success=success,
                optimization=optimization,
                created_at=request.created_at,
                correlation_id=context.correlation_id,
                causation_id=context.causation_id,
                trace_id=context.trace_id,
                tenant_id=context.tenant_id,
                error=error_message,
            )
            self._results[request.request_id] = result
        event_name = (
            "LearningOptimizationCompleted"
            if success
            else "LearningOptimizationFailed"
        )
        event_type = EventType.COMPLETE if success else EventType.FAILURE
        result_context = self._publish(
            event_name,
            event_type,
            {"result": result.to_dict(), "request": request.to_dict()},
            context,
        )
        with self._lock:
            self._last_context = result_context
        return result

    @staticmethod
    def _optimization_success(optimization: Mapping[str, Any]) -> bool:
        execution = optimization.get("execution")
        if not execution:
            return True
        if not isinstance(execution, (tuple, list)):
            return False
        values = tuple(
            item.get("success")
            for item in execution
            if isinstance(item, Mapping)
        )
        return bool(values) and all(value is True for value in values)

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
            error(
                "Learning optimizer boundary event publication failed",
                {"event_name": event_name, "error": str(exc)},
            )
            return context
