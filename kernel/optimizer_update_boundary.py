from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, unique
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

__all__ = [
    "OptimizationEvidenceRecorder",
    "OptimizationUpdate",
    "OptimizationUpdateBoundary",
    "OptimizationUpdateKind",
    "OptimizationUpdateRequest",
    "OptimizationUpdateResult",
]


@unique
class OptimizationUpdateKind(StrEnum):
    RUNTIME = "runtime"
    POLICY = "policy"
    MEMORY = "memory"


_ACTION_TARGETS: dict[str, OptimizationUpdateKind] = {
    "reduce_context_depth": OptimizationUpdateKind.RUNTIME,
    "simplify_policy": OptimizationUpdateKind.POLICY,
    "compress_memory": OptimizationUpdateKind.MEMORY,
}


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


class OptimizationUpdateBackend(Protocol):
    @property
    def optimizer_id(self) -> str: ...

    def execute_actions(
        self,
        actions: list[str] | tuple[str, ...],
        context: Mapping[str, Any] | None = None,
        *,
        rollback_on_failure: bool = True,
    ) -> tuple[Any, ...]: ...


class OptimizationEvidenceRecorder(Protocol):
    def record(
        self,
        result: OptimizationUpdateResult,
        *,
        context: EventPropagationContext | None = None,
        created_at: datetime | None = None,
    ) -> Any: ...


@dataclass(frozen=True, slots=True)
class OptimizationUpdate:
    action: str
    target: OptimizationUpdateKind
    success: bool
    changed: bool
    result: Any = None
    rolled_back: bool = False
    error: str | None = None

    def __post_init__(self) -> None:
        _text("action", self.action)
        if not isinstance(self.target, OptimizationUpdateKind):
            raise TypeError("target must be OptimizationUpdateKind")
        if not isinstance(self.success, bool):
            raise TypeError("success must be bool")
        if not isinstance(self.changed, bool):
            raise TypeError("changed must be bool")
        if not isinstance(self.rolled_back, bool):
            raise TypeError("rolled_back must be bool")
        if self.error is not None:
            _text("error", self.error)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "target": self.target.value,
            "success": self.success,
            "changed": self.changed,
            "result": self.result,
            "rolled_back": self.rolled_back,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class OptimizationUpdateRequest:
    request_id: str
    optimization_id: str
    actions: tuple[str, ...]
    created_at: datetime
    correlation_id: str
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in (
            ("request_id", self.request_id),
            ("optimization_id", self.optimization_id),
            ("correlation_id", self.correlation_id),
        ):
            _text(name, value)
        normalized = tuple(_text("action", action) for action in self.actions)
        if len(normalized) != len(set(normalized)):
            raise ValueError("actions must be unique")
        if any(action not in _ACTION_TARGETS for action in normalized):
            raise ValueError("unsupported optimization update action")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        for field_name, field_value in (
            ("causation_id", self.causation_id),
            ("trace_id", self.trace_id),
            ("tenant_id", self.tenant_id),
        ):
            if field_value is not None:
                _text(field_name, field_value)
        object.__setattr__(self, "actions", normalized)
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))
        object.__setattr__(self, "metadata", _mapping(self.metadata))

    @classmethod
    def from_optimization(
        cls,
        optimization: Mapping[str, Any],
        *,
        context: EventPropagationContext,
        created_at: datetime | None = None,
    ) -> OptimizationUpdateRequest:
        if not isinstance(optimization, Mapping):
            raise TypeError("optimization must be a mapping")
        optimization_id = _text("optimization_id", optimization.get("optimizer_id"))
        rebalance = optimization.get("rebalance")
        if not isinstance(rebalance, Mapping):
            raise TypeError("optimization.rebalance must be a mapping")
        raw_actions = rebalance.get("actions", ())
        if not isinstance(raw_actions, (list, tuple)):
            raise TypeError("optimization.rebalance.actions must be a sequence")
        actions = tuple(raw_actions)
        request_id = short_id(
            {"optimization_id": optimization_id, "actions": actions},
            prefix="optimization-update:",
        )
        return cls(
            request_id=request_id,
            optimization_id=optimization_id,
            actions=actions,
            created_at=created_at or datetime.now(UTC),
            correlation_id=context.correlation_id,
            causation_id=context.causation_id,
            trace_id=context.trace_id,
            tenant_id=context.tenant_id,
            metadata={"optimizer_id": optimization_id},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "optimization_id": self.optimization_id,
            "actions": list(self.actions),
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class OptimizationUpdateResult:
    request_id: str
    optimization_id: str
    success: bool
    updates: tuple[OptimizationUpdate, ...]
    created_at: datetime
    correlation_id: str
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("request_id", self.request_id),
            ("optimization_id", self.optimization_id),
            ("correlation_id", self.correlation_id),
        ):
            _text(name, value)
        if not isinstance(self.success, bool):
            raise TypeError("success must be bool")
        if not all(isinstance(item, OptimizationUpdate) for item in self.updates):
            raise TypeError("updates must contain OptimizationUpdate")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        for field_name, field_value in (
            ("causation_id", self.causation_id),
            ("trace_id", self.trace_id),
            ("tenant_id", self.tenant_id),
        ):
            if field_value is not None:
                _text(field_name, field_value)
        if self.error is not None:
            _text("error", self.error)
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))

    @property
    def changed(self) -> bool:
        return any(item.changed and not item.rolled_back for item in self.updates)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "optimization_id": self.optimization_id,
            "success": self.success,
            "changed": self.changed,
            "updates": [item.to_dict() for item in self.updates],
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "error": self.error,
        }


class OptimizationUpdateBoundary:
    __slots__ = (
        "_event_bus",
        "_event_publisher",
        "_evidence_boundary",
        "_inflight",        "_last_context",
        "_lock",
        "_results",
        "_subscriber_id",
        "optimizer",
    )

    def __init__(
        self,
        optimizer: OptimizationUpdateBackend,
        event_publisher: EventPublisher | None = None,
        *,
        subscriber_id: str = "optimizer.update-boundary",
        evidence_boundary: OptimizationEvidenceRecorder | None = None,
    ) -> None:
        if optimizer is None or not callable(getattr(optimizer, "execute_actions", None)):
            raise TypeError("optimizer must provide execute_actions")
        if event_publisher is not None and not isinstance(event_publisher, EventPublisher):
            raise TypeError("event_publisher must be EventPublisher or None")
        if evidence_boundary is not None and not callable(getattr(evidence_boundary, "record", None)):
            raise TypeError("evidence_boundary must provide record")
        self.optimizer = optimizer
        self._evidence_boundary = evidence_boundary
        self._event_publisher = event_publisher
        self._event_bus: EventBus | None = None
        self._inflight: dict[str, ThreadEvent] = {}
        self._last_context: EventPropagationContext | None = None
        self._lock = RLock()
        self._results: dict[str, OptimizationUpdateResult] = {}
        self._subscriber_id = _text("subscriber_id", subscriber_id)
        self._configure()

    @property
    def evidence_boundary(self) -> OptimizationEvidenceRecorder | None:
        return self._evidence_boundary

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

    def records(self) -> tuple[OptimizationUpdateResult, ...]:
        with self._lock:
            return tuple(self._results[key] for key in sorted(self._results))

    def get(self, request_id: str) -> OptimizationUpdateResult | None:
        _text("request_id", request_id)
        with self._lock:
            return self._results.get(request_id)

    def request(
        self,
        optimization: Mapping[str, Any],
        *,
        context: EventPropagationContext,
        created_at: datetime | None = None,
    ) -> OptimizationUpdateResult:
        if not isinstance(context, EventPropagationContext):
            raise TypeError("context must be EventPropagationContext")
        request = OptimizationUpdateRequest.from_optimization(
            optimization,
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
                leader = True
            else:
                leader = False
        if not leader:
            waiter.wait()
            result = self.get(request.request_id)
            if result is None:
                raise RuntimeError(f"optimization update result not produced: {request.request_id}")
            return result
        try:
            publisher = self.event_publisher
            event_bus = self._event_bus
            if publisher is None or event_bus is None:
                return self._execute(request, context)
            self._publish(
                "OptimizationUpdateRequested",
                EventType.START,
                {"request": request.to_dict()},
                context,
            )
            result = self.get(request.request_id)
            if result is None:
                raise RuntimeError(f"optimization update result not produced: {request.request_id}")
            return result
        finally:
            with self._lock:
                waiter = self._inflight.pop(request.request_id, None)
                if waiter is not None:
                    waiter.set()

    def _configure(self) -> None:
        publisher = self.event_publisher
        event_bus = getattr(publisher, "event_bus", None) if publisher is not None else None
        if event_bus is not None and not isinstance(event_bus, EventBus):
            event_bus = None
        with self._lock:
            previous = self._event_bus
            if previous is event_bus:
                return
            self._event_bus = event_bus
        if previous is not None:
            with suppress(KeyError):
                previous.unsubscribe(self._subscriber_id)
        if event_bus is not None:
            event_bus.subscribe(
                EventSubscription(
                    subscriber_id=self._subscriber_id,
                    handler=self._handle_request,
                    event_name="OptimizationUpdateRequested",
                    priority=100,
                ),
                replace=True,
            )

    def _handle_request(self, event: Event) -> None:
        payload = event.payload.get("request")
        if not isinstance(payload, Mapping):
            return
        try:
            request = self._from_dict(payload)
            self._execute(request, EventPropagationContext.from_event(event))
        except Exception as exc:
            error("Optimization update boundary event handling failed", {"error": str(exc)})

    @staticmethod
    def _from_dict(data: Mapping[str, Any]) -> OptimizationUpdateRequest:
        created_at = data.get("created_at")
        timestamp = created_at if isinstance(created_at, datetime) else datetime.fromisoformat(str(created_at))
        raw_actions = data.get("actions", ())
        actions = tuple(raw_actions) if isinstance(raw_actions, (list, tuple)) else ()
        metadata = data.get("metadata")
        return OptimizationUpdateRequest(
            request_id=_text("request_id", data.get("request_id")),
            optimization_id=_text("optimization_id", data.get("optimization_id")),
            actions=actions,
            created_at=timestamp,
            correlation_id=_text("correlation_id", data.get("correlation_id")),
            causation_id=data.get("causation_id"),
            trace_id=data.get("trace_id"),
            tenant_id=data.get("tenant_id"),
            metadata=metadata if isinstance(metadata, Mapping) else {},
        )

    def _execute(
        self,
        request: OptimizationUpdateRequest,
        context: EventPropagationContext,
    ) -> OptimizationUpdateResult:
        with self._lock:
            existing = self._results.get(request.request_id)
            if existing is not None:
                return existing
        try:
            if request.actions:
                raw_results = self.optimizer.execute_actions(
                    request.actions,
                    {
                        "correlation_id": context.correlation_id,
                        "causation_id": context.causation_id,
                        "trace_id": context.trace_id,
                        "tenant_id": context.tenant_id,
                    },
                    rollback_on_failure=True,
                )
            else:
                raw_results = ()
            updates = tuple(self._normalize(item) for item in raw_results)
            success = all(item.success for item in updates) if updates else True
            error_message = next((item.error for item in updates if item.error), None)
        except Exception as exc:
            updates = ()
            success = False
            error_message = str(exc)
        result = OptimizationUpdateResult(
            request_id=request.request_id,
            optimization_id=request.optimization_id,
            success=success,
            updates=updates,
            created_at=request.created_at,
            correlation_id=context.correlation_id,
            causation_id=context.causation_id,
            trace_id=context.trace_id,
            tenant_id=context.tenant_id,
            error=error_message,
        )
        with self._lock:
            self._results[request.request_id] = result
        result_context = context
        for update in result.updates:
            if update.success and update.changed and not update.rolled_back:
                event_name = {
                    OptimizationUpdateKind.RUNTIME: "ContextUpdated",
                    OptimizationUpdateKind.POLICY: "PolicyUpdated",
                    OptimizationUpdateKind.MEMORY: "MemoryUpdated",
                }[update.target]
                event_category = {
                    OptimizationUpdateKind.RUNTIME: Category.RUNTIME,
                    OptimizationUpdateKind.POLICY: Category.ACTION,
                    OptimizationUpdateKind.MEMORY: Category.MEMORY,
                }[update.target]
                result_context = self._publish(
                    event_name,
                    EventType.UPDATED,
                    {
                        "optimization_id": request.optimization_id,
                        "request_id": request.request_id,
                        "action": update.action,
                        "target": update.target.value,
                        "change": update.result,
                    },
                    result_context,
                    category=event_category,
                )
        result_context = self._publish(
            "OptimizationUpdateCompleted" if result.success else "OptimizationUpdateFailed",
            EventType.COMPLETE if result.success else EventType.FAILURE,
            {"request": request.to_dict(), "result": result.to_dict()},
            result_context,
        )
        evidence_boundary = self._evidence_boundary
        if evidence_boundary is not None and self._event_bus is None:
            try:
                evidence_boundary.record(
                    result,
                    context=result_context,
                    created_at=result.created_at,
                )
            except Exception as exc:
                error(
                    "Optimization evidence recording failed",
                    {"request_id": result.request_id, "error": str(exc)},
                )
        with self._lock:
            self._last_context = result_context
        return result

    @staticmethod
    def _normalize(item: Any) -> OptimizationUpdate:
        action = str(getattr(item, "action", ""))
        target = _ACTION_TARGETS.get(action)
        if target is None:
            raise ValueError(f"unsupported optimization action result: {action}")
        value = getattr(item, "result", None)
        changed = bool(value.get("changed", False)) if isinstance(value, Mapping) else bool(getattr(item, "success", False))
        return OptimizationUpdate(
            action=action,
            target=target,
            success=bool(getattr(item, "success", False)),
            changed=changed,
            result=value,
            rolled_back=bool(getattr(item, "rolled_back", False)),
            error=getattr(item, "error", None),
        )

    def _publish(
        self,
        event_name: str,
        event_type: EventType,
        payload: Mapping[str, Any],
        context: EventPropagationContext,
        *,
        category: Category = Category.ACTION,
    ) -> EventPropagationContext:
        publisher = self.event_publisher
        if publisher is None:
            return context
        try:
            event = Event.create(
                event_name=event_name,
                producer=self._subscriber_id,
                payload=dict(payload),
                category=category,
                event_type=event_type,
                correlation_id=context.correlation_id,
                causation_id=context.causation_id,
                trace_id=context.trace_id,
                tenant_id=context.tenant_id,
            )
            publisher.publish(event)
            return context.next(event.metadata.event_id)
        except Exception as exc:
            error("Optimization update event publication failed", {"event_name": event_name, "error": str(exc)})
            return context
