from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Event as ThreadEvent
from threading import RLock
from types import MappingProxyType
from typing import Any

from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.utils.hash import short_id
from foundation.utils.logging import error
from foundation.version import EVIDENCE_SCHEMA_VERSION
from infrastructure.event_bus import EventBus, EventPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from infrastructure.security import EvidenceRecord, EvidenceStore
from kernel.optimizer_update_boundary import OptimizationUpdateResult

__all__ = [
    "OptimizationEvidenceBoundary",
    "OptimizationEvidenceResult",
]


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


@dataclass(frozen=True, slots=True)
class OptimizationEvidenceResult:
    request_id: str
    recorded: bool
    evidence: EvidenceRecord | None
    created_at: datetime
    correlation_id: str
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    error: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _text("request_id", self.request_id)
        if not isinstance(self.recorded, bool):
            raise TypeError("recorded must be bool")
        if self.evidence is not None and not isinstance(self.evidence, EvidenceRecord):
            raise TypeError("evidence must be EvidenceRecord or None")
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
        if self.recorded != (self.evidence is not None):
            raise ValueError("recorded must match evidence presence")
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))
        object.__setattr__(self, "metadata", _mapping(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "recorded": self.recorded,
            "evidence": None if self.evidence is None else self.evidence.to_dict(),
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "error": self.error,
            "metadata": dict(self.metadata),
        }


class OptimizationEvidenceBoundary:
    __slots__ = (
        "_event_bus",
        "_event_publisher",
        "_inflight",
        "_last_context",
        "_lock",
        "_results",
        "_store",
        "_subscriber_id",
    )

    def __init__(
        self,
        evidence_store: EvidenceStore | None = None,
        event_publisher: EventPublisher | None = None,
        *,
        subscriber_id: str = "optimizer.evidence-boundary",
    ) -> None:
        if evidence_store is not None and not isinstance(evidence_store, EvidenceStore):
            raise TypeError("evidence_store must be EvidenceStore or None")
        if event_publisher is not None and not isinstance(event_publisher, EventPublisher):
            raise TypeError("event_publisher must be EventPublisher or None")
        self._store = evidence_store or EvidenceStore()
        self._event_publisher = event_publisher
        self._event_bus: EventBus | None = None
        self._lock = RLock()
        self._inflight: dict[str, ThreadEvent] = {}
        self._results: dict[str, OptimizationEvidenceResult] = {}
        self._last_context: EventPropagationContext | None = None
        self._subscriber_id = _text("subscriber_id", subscriber_id)
        self._configure()

    @property
    def evidence_store(self) -> EvidenceStore:
        return self._store

    @property
    def event_publisher(self) -> EventPublisher | None:
        with self._lock:
            return self._event_publisher

    @property
    def propagation_context(self) -> EventPropagationContext | None:
        with self._lock:
            return self._last_context

    def records(self) -> tuple[OptimizationEvidenceResult, ...]:
        with self._lock:
            return tuple(self._results.values())

    def get(self, request_id: str) -> OptimizationEvidenceResult | None:
        with self._lock:
            return self._results.get(request_id)

    def set_event_publisher(self, publisher: EventPublisher | None) -> None:
        if publisher is not None and not isinstance(publisher, EventPublisher):
            raise TypeError("publisher must implement EventPublisher")
        with self._lock:
            self._event_publisher = publisher
        self._configure()

    def record(
        self,
        result: OptimizationUpdateResult,
        *,
        context: EventPropagationContext | None = None,
        created_at: datetime | None = None,
    ) -> OptimizationEvidenceResult:
        if not isinstance(result, OptimizationUpdateResult):
            raise TypeError("result must be OptimizationUpdateResult")
        propagation = context or EventPropagationContext.create(
            correlation_id=result.correlation_id,
            causation_id=result.causation_id,
            trace_id=result.trace_id,
            tenant_id=result.tenant_id,
        )
        now = (created_at or result.created_at).astimezone(UTC)
        material_updates = tuple(
            update
            for update in result.updates
            if update.success and update.changed and not update.rolled_back
        )
        if not material_updates:
            outcome = OptimizationEvidenceResult(
                request_id=result.request_id,
                recorded=False,
                evidence=None,
                created_at=now,
                correlation_id=propagation.correlation_id,
                causation_id=propagation.causation_id,
                trace_id=propagation.trace_id,
                tenant_id=propagation.tenant_id,
                metadata={"material_changes": 0},
            )
            with self._lock:
                self._results[result.request_id] = outcome
                self._last_context = propagation
            return outcome

        with self._lock:
            existing = self._results.get(result.request_id)
            if existing is not None:
                return existing
            waiter = self._inflight.get(result.request_id)
            if waiter is None:
                waiter = ThreadEvent()
                self._inflight[result.request_id] = waiter
                leader = True
            else:
                leader = False
        if not leader:
            waiter.wait()
            resolved = self.get(result.request_id)
            if resolved is None:
                raise RuntimeError(f"optimization evidence result not produced: {result.request_id}")
            return resolved

        try:
            try:
                evidence = self._store.register(
                    self._build_evidence(result, material_updates, propagation, now)
                )
                outcome = OptimizationEvidenceResult(
                    request_id=result.request_id,
                    recorded=True,
                    evidence=evidence,
                    created_at=now,
                    correlation_id=propagation.correlation_id,
                    causation_id=propagation.causation_id,
                    trace_id=propagation.trace_id,
                    tenant_id=propagation.tenant_id,
                    metadata={"material_changes": len(material_updates)},
                )
            except Exception as exc:
                outcome = OptimizationEvidenceResult(
                    request_id=result.request_id,
                    recorded=False,
                    evidence=None,
                    created_at=now,
                    correlation_id=propagation.correlation_id,
                    causation_id=propagation.causation_id,
                    trace_id=propagation.trace_id,
                    tenant_id=propagation.tenant_id,
                    error=str(exc),
                    metadata={"material_changes": len(material_updates)},
                )
            with self._lock:
                self._results[result.request_id] = outcome
                self._last_context = propagation
            if outcome.recorded:
                published = self._publish(
                    "OptimizationEvidenceRecorded",
                    EventType.CREATED,
                    {
                        "request_id": result.request_id,
                        "optimization_id": result.optimization_id,
                        "evidence_id": outcome.evidence.evidence_id if outcome.evidence is not None else None,
                        "material_changes": len(material_updates),
                    },
                    propagation,
                )
                with self._lock:
                    self._last_context = published
            else:
                self._publish(
                    "OptimizationEvidenceFailed",
                    EventType.FAILURE,
                    {
                        "request_id": result.request_id,
                        "optimization_id": result.optimization_id,
                        "material_changes": len(material_updates),
                        "error": outcome.error,
                    },
                    propagation,
                )
            return outcome
        finally:
            with self._lock:
                waiter = self._inflight.pop(result.request_id, None)
                if waiter is not None:
                    waiter.set()

    def _configure(self) -> None:
        with self._lock:
            publisher = self._event_publisher
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
                    handler=self._handle_update_completed,
                    event_name="OptimizationUpdateCompleted",
                    priority=-50,
                ),
                replace=True,
            )

    def _handle_update_completed(self, event: Event) -> None:
        payload = event.payload.get("result")
        if not isinstance(payload, Mapping):
            return
        try:
            result = self._from_dict(payload)
            self.record(
                result,
                context=EventPropagationContext.from_event(event),
                created_at=event.timestamp,
            )
        except Exception as exc:
            error(
                "Optimization evidence boundary event handling failed",
                {"error": str(exc), "event_id": event.id},
            )

    @staticmethod
    def _from_dict(data: Mapping[str, Any]) -> OptimizationUpdateResult:
        raw_updates = data.get("updates", ())
        if not isinstance(raw_updates, (list, tuple)):
            raise TypeError("result.updates must be a sequence")
        from kernel.optimizer_update_boundary import OptimizationUpdate, OptimizationUpdateKind

        updates: list[OptimizationUpdate] = []
        for item in raw_updates:
            if not isinstance(item, Mapping):
                raise TypeError("result.updates entries must be mappings")
            target = OptimizationUpdateKind(_text("target", item.get("target")))
            updates.append(
                OptimizationUpdate(
                    action=_text("action", item.get("action")),
                    target=target,
                    success=bool(item.get("success")),
                    changed=bool(item.get("changed")),
                    result=item.get("result"),
                    rolled_back=bool(item.get("rolled_back")),
                    error=item.get("error"),
                )
            )
        created_at = data.get("created_at")
        timestamp = created_at if isinstance(created_at, datetime) else datetime.fromisoformat(str(created_at))
        return OptimizationUpdateResult(
            request_id=_text("request_id", data.get("request_id")),
            optimization_id=_text("optimization_id", data.get("optimization_id")),
            success=bool(data.get("success")),
            updates=tuple(updates),
            created_at=timestamp,
            correlation_id=_text("correlation_id", data.get("correlation_id")),
            causation_id=data.get("causation_id"),
            trace_id=data.get("trace_id"),
            tenant_id=data.get("tenant_id"),
            error=data.get("error"),
        )

    @staticmethod
    def _build_evidence(
        result: OptimizationUpdateResult,
        material_updates: tuple[Any, ...],
        context: EventPropagationContext,
        created_at: datetime,
    ) -> EvidenceRecord:
        evidence_id = short_id(
            result.request_id,
            prefix="optimization:",
        )
        payload = {
            "optimization_id": result.optimization_id,
            "request_id": result.request_id,
            "success": result.success,
            "changed": result.changed,
            "material_changes": len(material_updates),
            "updates": [item.to_dict() for item in material_updates],
            "correlation_id": context.correlation_id,
            "causation_id": context.causation_id,
            "trace_id": context.trace_id,
            "tenant_id": context.tenant_id,
        }
        return EvidenceRecord.create(
            evidence_id=evidence_id,
            kind="optimization",
            source="optimizer",
            subject_id=result.request_id,
            version=EVIDENCE_SCHEMA_VERSION,
            trace_id=context.trace_id,
            collected_at=created_at.isoformat(),
            payload=payload,
        )

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
                payload=dict(payload),
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
                "Optimization evidence event publication failed",
                {"event_name": event_name, "error": str(exc)},
            )
            return context
