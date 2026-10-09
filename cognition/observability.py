from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from threading import RLock
from typing import Any

from cognition.contracts import CognitiveResult, CognitiveResultStatus
from foundation.Enums import Category
from foundation.Enums.event import EventType
from foundation.version import EVENT_SCHEMA_VERSION, EVIDENCE_SCHEMA_VERSION
from infrastructure.event_bus import EventPublisher
from infrastructure.events import Event, EventPropagationContext
from infrastructure.security import EvidenceRecord, EvidenceStore

__all__ = ["CognitionObservability", "CognitionObservationReport"]


@dataclass(frozen=True, slots=True)
class CognitionObservationReport:
    result_id: str
    event_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def successful(self) -> bool:
        return not self.errors


def _mapping(value: object, name: str) -> Mapping[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise TypeError(f"result output field {name!r} must be a mapping")
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _event_type(status: CognitiveResultStatus) -> EventType:
    if status is CognitiveResultStatus.SUCCESS:
        return EventType.SUCCESS
    if status is CognitiveResultStatus.FAILURE:
        return EventType.FAILURE
    return EventType.UPDATED


class CognitionObservability:
    """Event and evidence observability for typed cognition results."""

    __slots__ = ("_event_publisher", "_evidence_store", "_lock", "_logger_name")

    def __init__(
        self,
        event_publisher: EventPublisher | None = None,
        evidence_store: EvidenceStore | None = None,
        *,
        logger_name: str = "sh3.cognition",
    ) -> None:
        if event_publisher is not None and not isinstance(event_publisher, EventPublisher):
            raise TypeError("event_publisher must be EventPublisher or None")
        if evidence_store is not None and not isinstance(evidence_store, EvidenceStore):
            raise TypeError("evidence_store must be EvidenceStore or None")
        _text(logger_name, "logger_name")
        self._lock = RLock()
        self._event_publisher = event_publisher
        self._evidence_store = evidence_store or EvidenceStore()
        self._logger_name = logger_name

    @property
    def event_publisher(self) -> EventPublisher | None:
        with self._lock:
            return self._event_publisher

    def set_event_publisher(self, event_publisher: EventPublisher | None) -> None:
        if event_publisher is not None and not isinstance(event_publisher, EventPublisher):
            raise TypeError("event_publisher must be EventPublisher or None")
        with self._lock:
            self._event_publisher = event_publisher

    @property
    def evidence_store(self) -> EvidenceStore:
        return self._evidence_store

    @property
    def logger_name(self) -> str:
        return self._logger_name

    def observe(self, result: CognitiveResult) -> CognitionObservationReport:
        if not isinstance(result, CognitiveResult):
            raise TypeError("result must be CognitiveResult")
        with self._lock:
            event_ids: list[str] = []
            evidence_ids: list[str] = []
            errors: list[str] = []
            output = result.output
            goal = _mapping(output.get("goal"), "goal")
            plan = _mapping(output.get("plan"), "plan")
            policy = _mapping(output.get("policy"), "policy")
            decision = _mapping(output.get("decision"), "decision")
            execution = _mapping(output.get("execution"), "execution")
            self._record_stage("policy", policy, result, evidence_ids, errors)
            self._record_stage("decision", decision, result, evidence_ids, errors)
            self._record_stage("execution", execution, result, evidence_ids, errors)
            self._record_result(result, evidence_ids, errors)
            initial_causation = result.causation_id
            if policy is not None:
                initial_causation = str(plan.get("plan_id")) if plan is not None and plan.get("plan_id") else initial_causation
            context = EventPropagationContext.create(
                correlation_id=result.correlation_id,
                causation_id=initial_causation,
                trace_id=result.trace_id,
                tenant_id=result.tenant_id,
            )
            if policy is not None:
                context = self._publish(
                    event_ids,
                    errors,
                    event_name="CognitionPolicyEvaluated",
                    event_type=EventType.VALIDATE,
                    category=Category.PLANNING,
                    payload={"goal": dict(goal or {}), "plan": dict(plan or {}), "policy": dict(policy)},
                    context=context,
                )
            if decision is not None:
                context = self._publish(
                    event_ids,
                    errors,
                    event_name="CognitionDecisionCreated",
                    event_type=EventType.CREATED,
                    category=Category.ACTION,
                    payload={
                        "goal": dict(goal or {}),
                        "plan": dict(plan or {}),
                        "policy": dict(policy or {}),
                        "decision": dict(decision),
                    },
                    context=context,
                )
            if execution is not None:
                execution_event_type = EventType.SUCCESS if bool(execution.get("success", False)) else EventType.FAILURE
                context = self._publish(
                    event_ids,
                    errors,
                    event_name="CognitionExecutionCompleted" if execution_event_type is EventType.SUCCESS else "CognitionExecutionFailed",
                    event_type=execution_event_type,
                    category=Category.EXECUTION,
                    payload={
                        "goal_id": result.goal_id,
                        "decision_id": decision.get("decision_id") if decision is not None else None,
                        "execution": dict(execution),
                    },
                    context=context,
                )
            self._publish(
                event_ids,
                errors,
                event_name="CognitionResultRecorded",
                event_type=_event_type(result.status),
                category=Category.EXECUTION if execution is not None else Category.ACTION,
                payload={"result": result.to_dict()},
                context=context,
            )
            return CognitionObservationReport(result.result_id, tuple(event_ids), tuple(evidence_ids), tuple(errors))

    def records(self) -> tuple[EvidenceRecord, ...]:
        with self._lock:
            return tuple(record for record in self._evidence_store.records() if record.source == "cognition")

    def get(self, evidence_id: str) -> EvidenceRecord | None:
        _text(evidence_id, "evidence_id")
        return self._evidence_store.get(evidence_id)

    def verify(self, evidence_id: str) -> bool:
        _text(evidence_id, "evidence_id")
        return self._evidence_store.verify(evidence_id)

    def _record_stage(
        self,
        stage: str,
        payload: Mapping[str, Any] | None,
        result: CognitiveResult,
        evidence_ids: list[str],
        errors: list[str],
    ) -> None:
        if payload is None:
            return
        try:
            subject_key = {"policy": "evaluation_id", "decision": "decision_id", "execution": "execution_id"}[stage]
            subject_id = _text(payload.get(subject_key), subject_key)
            evidence_id = f"cognition.{stage}:{subject_id}"
            existing = self._evidence_store.get(evidence_id)
            if existing is not None:
                if not existing.verify():
                    raise ValueError(f"cognition evidence integrity verification failed: {evidence_id}")
                evidence_ids.append(existing.evidence_id)
                return
            record = EvidenceRecord.create(
                evidence_id=evidence_id,
                kind=f"cognition.{stage}",
                source="cognition",
                subject_id=subject_id,
                version=EVIDENCE_SCHEMA_VERSION,
                payload={
                    "stage": stage,
                    "result_id": result.result_id,
                    "goal_id": result.goal_id,
                    "correlation_id": result.correlation_id,
                    "trace_id": result.trace_id,
                    "tenant_id": result.tenant_id,
                    "event_schema_version": EVENT_SCHEMA_VERSION,
                    "data": dict(payload),
                },
                trace_id=result.trace_id,
            )
            evidence_ids.append(self._evidence_store.register(record).evidence_id)
        except Exception as exc:
            errors.append(f"evidence:{stage}:{type(exc).__name__}:{exc}")

    def _record_result(self, result: CognitiveResult, evidence_ids: list[str], errors: list[str]) -> None:
        try:
            evidence_id = f"cognition.result:{result.result_id}"
            existing = self._evidence_store.get(evidence_id)
            if existing is not None:
                if not existing.verify():
                    raise ValueError(f"cognition evidence integrity verification failed: {evidence_id}")
                evidence_ids.append(existing.evidence_id)
                return
            record = EvidenceRecord.create(
                evidence_id=evidence_id,
                kind="cognition.result",
                source="cognition",
                subject_id=result.result_id,
                version=EVIDENCE_SCHEMA_VERSION,
                payload={
                    "stage": "result",
                    "result": result.to_dict(),
                    "correlation_id": result.correlation_id,
                    "causation_id": result.causation_id,
                    "trace_id": result.trace_id,
                    "tenant_id": result.tenant_id,
                    "event_schema_version": EVENT_SCHEMA_VERSION,
                },
                trace_id=result.trace_id,
            )
            evidence_ids.append(self._evidence_store.register(record).evidence_id)
        except Exception as exc:
            errors.append(f"evidence:result:{type(exc).__name__}:{exc}")

    def _publish(
        self,
        event_ids: list[str],
        errors: list[str],
        *,
        event_name: str,
        event_type: EventType,
        category: Category,
        payload: Mapping[str, Any],
        context: EventPropagationContext,
    ) -> EventPropagationContext:
        publisher = self._event_publisher
        if publisher is None:
            return context
        try:
            event = Event.create(
                event_name=event_name,
                producer="cognition.observability",
                payload=payload,
                category=category,
                event_type=event_type,
                correlation_id=context.correlation_id,
                causation_id=context.causation_id,
                trace_id=context.trace_id,
                tenant_id=context.tenant_id,
            )
            publisher.publish(event)
            event_ids.append(event.id)
            return context.next(event.id)
        except Exception as exc:
            errors.append(f"event:{event_name}:{type(exc).__name__}:{exc}")
            return context
