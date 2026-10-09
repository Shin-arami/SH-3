from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Event as ThreadEvent
from threading import RLock
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from cognition.feedback import CognitiveFeedbackKind
from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.utils.hash import short_id
from foundation.utils.logging import error
from foundation.version import EVENT_SCHEMA_VERSION, EVIDENCE_SCHEMA_VERSION
from infrastructure.event_bus import EventPublisher
from infrastructure.events import Event, EventPropagationContext
from infrastructure.security import EvidenceRecord, EvidenceStore

if TYPE_CHECKING:
    from kernel.learning_feedback_loop import LearningClosedLoopReport

__all__ = [
    "LearningClosedLoopEvidenceBoundary",
    "LearningClosedLoopEvidenceResult",
]


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


@dataclass(frozen=True, slots=True)
class LearningClosedLoopEvidenceResult:
    cycle_id: str
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
        _text("cycle_id", self.cycle_id)
        if not isinstance(self.recorded, bool):
            raise TypeError("recorded must be bool")
        if self.evidence is not None and not isinstance(self.evidence, EvidenceRecord):
            raise TypeError("evidence must be EvidenceRecord or None")
        if self.recorded != (self.evidence is not None):
            raise ValueError("recorded must match evidence presence")
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
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))
        object.__setattr__(self, "metadata", _mapping(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
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


class LearningClosedLoopEvidenceBoundary:
    __slots__ = (
        "_event_publisher",
        "_inflight",
        "_last_context",
        "_lock",
        "_results",
        "_store",
    )

    def __init__(
        self,
        evidence_store: EvidenceStore | None = None,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        if evidence_store is not None and not isinstance(evidence_store, EvidenceStore):
            raise TypeError("evidence_store must be EvidenceStore or None")
        if event_publisher is not None and not isinstance(event_publisher, EventPublisher):
            raise TypeError("event_publisher must be EventPublisher or None")
        self._store = evidence_store if evidence_store is not None else EvidenceStore()
        self._event_publisher = event_publisher
        self._lock = RLock()
        self._inflight: dict[str, ThreadEvent] = {}
        self._results: dict[str, LearningClosedLoopEvidenceResult] = {}
        self._last_context: EventPropagationContext | None = None

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

    def records(self) -> tuple[LearningClosedLoopEvidenceResult, ...]:
        with self._lock:
            return tuple(self._results.values())

    def get(self, cycle_id: str) -> LearningClosedLoopEvidenceResult | None:
        with self._lock:
            return self._results.get(cycle_id)

    def set_event_publisher(self, publisher: EventPublisher | None) -> None:
        if publisher is not None and not isinstance(publisher, EventPublisher):
            raise TypeError("publisher must implement EventPublisher")
        with self._lock:
            self._event_publisher = publisher

    def record(
        self,
        report: LearningClosedLoopReport,
        *,
        context: EventPropagationContext | None = None,
        created_at: datetime | None = None,
    ) -> LearningClosedLoopEvidenceResult:
        from kernel.learning_feedback_loop import LearningClosedLoopReport

        if not isinstance(report, LearningClosedLoopReport):
            raise TypeError("report must be LearningClosedLoopReport")
        propagation = context or EventPropagationContext.create(
            correlation_id=report.correlation_id,
            causation_id=report.causation_id,
            trace_id=report.trace_id,
            tenant_id=report.tenant_id,
        )
        timestamp = created_at or report.created_at
        if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        now = timestamp.astimezone(UTC)
        with self._lock:
            existing = self._results.get(report.cycle_id)
            if existing is not None:
                return existing
            waiter = self._inflight.get(report.cycle_id)
            if waiter is None:
                waiter = ThreadEvent()
                self._inflight[report.cycle_id] = waiter
                leader = True
            else:
                leader = False
        if not leader:
            waiter.wait()
            resolved = self.get(report.cycle_id)
            if resolved is None:
                raise RuntimeError(
                    f"closed-loop evidence result not produced: {report.cycle_id}"
                )
            return resolved

        related_evidence_ids: tuple[str, ...] = ()
        try:
            related_evidence_ids = self._related_optimization_evidence(propagation)
            evidence = self._build_evidence(
                report,
                propagation,
                now,
                related_evidence_ids,
            )
            registered = self._store.register(evidence)
            outcome = LearningClosedLoopEvidenceResult(
                cycle_id=report.cycle_id,
                recorded=True,
                evidence=registered,
                created_at=now,
                correlation_id=propagation.correlation_id,
                causation_id=propagation.causation_id,
                trace_id=propagation.trace_id,
                tenant_id=propagation.tenant_id,
                metadata={
                    "status": report.status.value,
                    "related_optimization_evidence": len(related_evidence_ids),
                },
            )
        except Exception as exc:
            outcome = LearningClosedLoopEvidenceResult(
                cycle_id=report.cycle_id,
                recorded=False,
                evidence=None,
                created_at=now,
                correlation_id=propagation.correlation_id,
                causation_id=propagation.causation_id,
                trace_id=propagation.trace_id,
                tenant_id=propagation.tenant_id,
                error=str(exc) or type(exc).__name__,
                metadata={"status": report.status.value},
            )
        with self._lock:
            self._results[report.cycle_id] = outcome
            self._last_context = propagation
            completion = self._inflight.pop(report.cycle_id, None)
            if completion is not None:
                completion.set()

        if outcome.recorded:
            published = self._publish(
                "LearningClosedLoopEvidenceRecorded",
                EventType.CREATED,
                {
                    "cycle_id": report.cycle_id,
                    "result_id": report.result_id,
                    "evidence_id": outcome.evidence.evidence_id if outcome.evidence is not None else "",
                    "status": report.status.value,
                    "success": report.status.value != "failed",
                    "related_optimization_evidence_ids": list(related_evidence_ids),
                },
                propagation,
            )
        else:
            published = self._publish(
                "LearningClosedLoopEvidenceFailed",
                EventType.FAILURE,
                {
                    "cycle_id": report.cycle_id,
                    "result_id": report.result_id,
                    "status": report.status.value,
                    "error": outcome.error or "evidence recording failed",
                },
                propagation,
            )
        with self._lock:
            self._last_context = published
        return outcome

    def _related_optimization_evidence(
        self,
        context: EventPropagationContext,
    ) -> tuple[str, ...]:
        related: list[str] = []
        for record in self._store.records():
            if record.kind != "optimization":
                continue
            if record.payload.get("correlation_id") != context.correlation_id:
                continue
            if context.trace_id is not None and record.trace_id != context.trace_id:
                continue
            related.append(record.evidence_id)
        return tuple(sorted(related))

    @staticmethod
    def _build_evidence(
        report: LearningClosedLoopReport,
        context: EventPropagationContext,
        created_at: datetime,
        related_evidence_ids: tuple[str, ...],
    ) -> EvidenceRecord:
        feedback = tuple(report.feedback)
        learning = next(
            (item for item in feedback if item.kind is CognitiveFeedbackKind.LEARNING),
            None,
        )
        optimization = next(
            (item for item in feedback if item.kind is CognitiveFeedbackKind.OPTIMIZATION),
            None,
        )
        healing = next(
            (item for item in feedback if item.kind is CognitiveFeedbackKind.SELF_HEALING),
            None,
        )
        aggregate = next(
            (item for item in feedback if item.kind is CognitiveFeedbackKind.CLOSED_LOOP),
            None,
        )
        status = report.status.value
        payload = {
            "cycle_id": report.cycle_id,
            "result_id": report.result_id,
            "goal_id": report.goal_id,
            "status": status,
            "cycle_success": status != "failed",
            "fully_successful": status == "completed",
            "recovered": status == "recovered",
            "learning_result": dict(report.learning_result),
            "optimization_result": None
            if report.optimization_result is None
            else dict(report.optimization_result),
            "healing_result": report.healing_result,
            "feedback": [item.to_dict() for item in feedback],
            "success_semantics": {
                "learning": None if learning is None else learning.success,
                "optimization": None if optimization is None else optimization.success,
                "self_healing": None if healing is None else healing.success,
                "aggregate": None if aggregate is None else aggregate.success,
            },
            "related_optimization_evidence_ids": list(related_evidence_ids),
            "event_schema_version": EVENT_SCHEMA_VERSION,
            "correlation_id": context.correlation_id,
            "causation_id": context.causation_id,
            "trace_id": context.trace_id,
            "tenant_id": context.tenant_id,
        }
        return EvidenceRecord.create(
            evidence_id=short_id(report.cycle_id, prefix="learning-closed-loop:"),
            kind="learning.closed_loop",
            source="kernel.learning_feedback_loop",
            subject_id=report.result_id,
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
                producer="learning.closed-loop.evidence-boundary",
                payload=dict(payload),
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
            error(
                "Learning closed-loop evidence event publication failed",
                {"event_name": event_name, "error": str(exc)},
            )
            return context
