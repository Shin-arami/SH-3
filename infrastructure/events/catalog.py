"""
SH-3 Complete Edition v2.0
Infrastructure Layer
Events Subsystem

catalog.py

Canonical event contract and catalog.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Final

from foundation.Enums.category import Category
from foundation.Enums.event import EventType

from .model import Event

__all__ = [
    "CANONICAL_EVENT_VERSION",
    "CanonicalEventCatalog",
    "EventDefinition",
]


CANONICAL_EVENT_VERSION: Final[str] = "1.0.0"


@dataclass(frozen=True, slots=True)
class EventDefinition:
    name: str
    version: str
    category: Category
    event_type: EventType
    required_payload: tuple[str, ...]
    optional_payload: tuple[str, ...]
    producer: str
    description: str
    compatibility: str = "backward-compatible"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("event name must not be empty")
        if not self.version:
            raise ValueError("event version must not be empty")
        if not isinstance(self.category, Category):
            raise TypeError("category must be Category")
        if not isinstance(self.event_type, EventType):
            raise TypeError("event_type must be EventType")
        if not self.producer:
            raise ValueError("event producer must not be empty")
        if not self.description:
            raise ValueError("event description must not be empty")
        if len(set(self.required_payload)) != len(self.required_payload):
            raise ValueError("required payload fields must be unique")
        if len(set(self.optional_payload)) != len(self.optional_payload):
            raise ValueError("optional payload fields must be unique")
        if set(self.required_payload) & set(self.optional_payload):
            raise ValueError("required and optional payload fields must not overlap")
        if any(not field for field in self.required_payload):
            raise ValueError("required payload fields must not be empty")
        if any(not field for field in self.optional_payload):
            raise ValueError("optional payload fields must not be empty")

    @property
    def key(self) -> tuple[str, str]:
        return self.name, self.version

    @property
    def payload_fields(self) -> tuple[str, ...]:
        return self.required_payload + self.optional_payload


class CanonicalEventCatalog:
    """Thread-safe canonical registry for SH-3 event contracts."""

    def __init__(
        self,
        definitions: tuple[EventDefinition, ...] | None = None,
    ) -> None:
        self._definitions: dict[tuple[str, str], EventDefinition] = {}
        self._lock = RLock()
        source = (
            CANONICAL_EVENT_DEFINITIONS
            if definitions is None
            else definitions
        )
        for definition in source:
            self.register(definition)

    def register(
        self,
        definition: EventDefinition,
        *,
        replace: bool = False,
    ) -> None:
        if not isinstance(definition, EventDefinition):
            raise TypeError("definition must be EventDefinition")
        with self._lock:
            if definition.key in self._definitions and not replace:
                raise ValueError(
                    f"event definition already registered: "
                    f"{definition.name}@{definition.version}"
                )
            self._definitions[definition.key] = definition

    def unregister(
        self,
        name: str,
        version: str = CANONICAL_EVENT_VERSION,
    ) -> EventDefinition:
        key = (name, version)
        with self._lock:
            try:
                return self._definitions.pop(key)
            except KeyError as exc:
                raise KeyError(
                    f"event definition not registered: {name}@{version}"
                ) from exc

    def get(
        self,
        name: str,
        version: str | None = None,
    ) -> EventDefinition:
        with self._lock:
            if version is not None:
                key = (name, version)
                try:
                    return self._definitions[key]
                except KeyError as exc:
                    raise KeyError(
                        f"event definition not registered: {name}@{version}"
                    ) from exc
            matches = tuple(
                definition
                for definition in self._definitions.values()
                if definition.name == name
            )
        if not matches:
            raise KeyError(f"event definition not registered: {name}")
        return max(matches, key=lambda item: _version_key(item.version))

    def require(
        self,
        name: str,
        version: str | None = None,
    ) -> EventDefinition:
        return self.get(name, version)

    def contains(
        self,
        name: str,
        version: str | None = None,
    ) -> bool:
        with self._lock:
            if version is not None:
                return (name, version) in self._definitions
            return any(
                definition.name == name
                for definition in self._definitions.values()
            )

    def all(self) -> tuple[EventDefinition, ...]:
        with self._lock:
            definitions = tuple(self._definitions.values())
        return tuple(
            sorted(
                definitions,
                key=lambda item: (item.name, _version_key(item.version)),
            )
        )

    def validate(self, event: Event) -> None:
        if not isinstance(event, Event):
            raise TypeError("event must be Event")
        definition = self.require(
            event.metadata.event_name,
            event.metadata.event_version,
        )
        issues: list[str] = []
        if event.category is not definition.category:
            issues.append(
                f"category mismatch: expected {definition.category.value}, "
                f"got {event.category.value}"
            )
        if event.event_type is not definition.event_type:
            issues.append(
                f"event_type mismatch: expected {definition.event_type.value}, "
                f"got {event.event_type.value}"
            )
        if event.metadata.producer != definition.producer:
            issues.append(
                f"producer mismatch: expected {definition.producer}, "
                f"got {event.metadata.producer}"
            )
        payload = event.payload
        missing = tuple(
            field for field in definition.required_payload if field not in payload
        )
        if missing:
            issues.append(f"missing payload fields: {', '.join(missing)}")
        unknown = tuple(
            sorted(
                field
                for field in payload
                if field not in definition.payload_fields
            )
        )
        if unknown:
            issues.append(f"unknown payload fields: {', '.join(unknown)}")
        if issues:
            raise ValueError("; ".join(issues))

    def clear(self) -> None:
        with self._lock:
            self._definitions.clear()

    def count(self) -> int:
        with self._lock:
            return len(self._definitions)


def _definition(
    name: str,
    category: Category,
    event_type: EventType,
    producer: str,
    required: tuple[str, ...] = (),
    optional: tuple[str, ...] = (),
    description: str = "",
) -> EventDefinition:
    return EventDefinition(
        name=name,
        version=CANONICAL_EVENT_VERSION,
        category=category,
        event_type=event_type,
        required_payload=required,
        optional_payload=optional,
        producer=producer,
        description=description or name,
    )


CANONICAL_EVENT_DEFINITIONS: Final[
    tuple[EventDefinition, ...]
] = (
    _definition(
        "ComponentRegistered",
        Category.COMPONENT,
        EventType.CREATED,
        "component",
        ("component",),
    ),
    _definition(
        "ComponentInitialized",
        Category.COMPONENT,
        EventType.INITIALIZED,
        "component",
        ("component",),
    ),
    _definition(
        "ComponentStarted",
        Category.COMPONENT,
        EventType.START,
        "component",
        ("component",),
    ),
    _definition(
        "ComponentStopped",
        Category.COMPONENT,
        EventType.STOP,
        "component",
        ("component",),
    ),
    _definition(
        "ComponentFailed",
        Category.COMPONENT,
        EventType.FAILURE,
        "component",
        ("component", "error"),
        ("details",),
    ),
    _definition(
        "ComponentRecovered",
        Category.COMPONENT,
        EventType.RESTART,
        "component",
        ("component",),
        ("details",),
    ),
    _definition(
        "RuntimeExecutionStarted",
        Category.EXECUTION,
        EventType.EXECUTE,
        "runtime",
        ("execution_id", "component"),
    ),
    _definition(
        "RuntimeExecutionCompleted",
        Category.EXECUTION,
        EventType.COMPLETE,
        "runtime",
        ("execution_id", "component", "result", "duration_ms", "success"),
    ),
    _definition(
        "RuntimeExecutionFailed",
        Category.EXECUTION,
        EventType.FAILURE,
        "runtime",
        ("execution_id", "component", "error"),
        ("duration_ms",),
    ),
    _definition(
        "RuntimePipelineStarted",
        Category.PIPELINE,
        EventType.START,
        "runtime",
        ("pipeline_id",),
    ),
    _definition(
        "RuntimePipelineCompleted",
        Category.PIPELINE,
        EventType.COMPLETE,
        "runtime",
        ("pipeline_id", "success"),
        ("duration_ms", "result"),
    ),
    _definition(
        "RuntimePipelineFailed",
        Category.PIPELINE,
        EventType.FAILURE,
        "runtime",
        ("pipeline_id", "error"),
        ("duration_ms",),
    ),
    _definition(
        "ServiceStarted",
        Category.COMPONENT,
        EventType.START,
        "service",
        ("service",),
    ),
    _definition(
        "ServiceStopped",
        Category.COMPONENT,
        EventType.STOP,
        "service",
        ("service",),
    ),
    _definition(
        "ServiceSuspended",
        Category.COMPONENT,
        EventType.PAUSE,
        "service",
        ("service",),
    ),
    _definition(
        "ServiceResumed",
        Category.COMPONENT,
        EventType.RESUME,
        "service",
        ("service",),
    ),
    _definition(
        "ServiceFailed",
        Category.COMPONENT,
        EventType.FAILURE,
        "service",
        ("service", "error"),
        ("details",),
    ),
    _definition(
        "ServiceRecovered",
        Category.COMPONENT,
        EventType.RESTART,
        "service",
        ("service",),
        ("details",),
    ),
    _definition(
        "KernelStarted",
        Category.COMPONENT,
        EventType.START,
        "kernel",
        ("kernel",),
    ),
    _definition(
        "KernelStopped",
        Category.COMPONENT,
        EventType.STOP,
        "kernel",
        ("kernel",),
    ),
    _definition(
        "KernelCycleStarted",
        Category.EXECUTION,
        EventType.EXECUTE,
        "kernel",
        ("cycle_id",),
    ),
    _definition(
        "KernelCycleCompleted",
        Category.EXECUTION,
        EventType.COMPLETE,
        "kernel",
        ("cycle_id", "success"),
        ("duration_ms", "result"),
    ),
    _definition(
        "KernelCycleFailed",
        Category.EXECUTION,
        EventType.FAILURE,
        "kernel",
        ("cycle_id", "error"),
        ("duration_ms",),
    ),
    _definition(
        "LearningStarted",
        Category.LEARNING,
        EventType.LEARNING_START,
        "learning",
        ("learning_id",),
    ),
    _definition(
        "LearningCompleted",
        Category.LEARNING,
        EventType.LEARNING_END,
        "learning",
        ("learning_id", "success"),
        ("duration_ms", "result"),
    ),
    _definition(
        "LearningFailed",
        Category.LEARNING,
        EventType.FAILURE,
        "learning",
        ("learning_id", "error"),
    ),
    _definition(
        "LearningRecordCreated",
        Category.LEARNING,
        EventType.CREATED,
        "learning",
        ("record_id", "key", "value"),
        ("success", "details"),
    ),
    _definition(
        "LearningResultRecorded",
        Category.LEARNING,
        EventType.UPDATED,
        "learning",
        ("learning_id", "success"),
        ("result", "details"),
    ),
    _definition(
        "LearningModelUpdated",
        Category.LEARNING,
        EventType.UPDATED,
        "learning",
        ("model_id",),
        ("version", "metrics"),
    ),
    _definition(
        "FailureDetected",
        Category.ACTION,
        EventType.FAILURE,
        "healing",
        ("failure_id", "component", "error"),
        ("severity", "details"),
    ),
    _definition(
        "RecoveryStarted",
        Category.ACTION,
        EventType.START,
        "healing",
        ("recovery_id", "failure_id", "strategy"),
    ),
    _definition(
        "RecoveryPlanned",
        Category.ACTION,
        EventType.CREATED,
        "healing",
        ("recovery_id", "failure_id", "strategy"),
        ("reason",),
    ),
    _definition(
        "RecoveryCompleted",
        Category.ACTION,
        EventType.COMPLETE,
        "healing",
        ("recovery_id", "failure_id", "strategy", "success"),
        ("details",),
    ),
    _definition(
        "RecoveryFailed",
        Category.ACTION,
        EventType.FAILURE,
        "healing",
        ("recovery_id", "failure_id", "strategy", "error"),
        ("details",),
    ),
    _definition(
        "HealingFeedbackRecorded",
        Category.LEARNING,
        EventType.CREATED,
        "healing",
        ("recovery_id", "success"),
        ("strategy", "feedback"),
    ),
    _definition(
        "RecoveryStrategyRequested",
        Category.STRATEGY,
        EventType.START,
        "healing.strategy",
        ("request_id", "failure_id"),
        ("candidates",),
        "Recovery strategy evaluation and selection request.",
    ),
    _definition(
        "RecoveryStrategyEvaluated",
        Category.STRATEGY,
        EventType.UPDATED,
        "healing.strategy",
        ("request_id", "failure_id", "evaluations"),
        (),
        "Recovery strategy evaluation result.",
    ),
    _definition(
        "RecoveryStrategySelected",
        Category.STRATEGY,
        EventType.COMPLETE,
        "healing.strategy",
        ("request_id", "failure_id", "strategy"),
        ("confidence", "evaluations"),
        "Deterministically selected recovery strategy.",
    ),
    _definition(
        "RecoveryStrategySelectionFailed",
        Category.STRATEGY,
        EventType.FAILURE,
        "healing.strategy",
        ("request_id", "failure_id", "error"),
        (),
        "Recovery strategy evaluation or selection failure.",
    ),
    _definition(
        "RecoveryExecutionRequested",
        Category.ACTION,
        EventType.START,
        "recovery.execution-boundary",
        ("request_id", "failure_id", "strategy"),
        (),
        "Recovery execution request.",
    ),
    _definition(
        "RecoveryExecutionCompleted",
        Category.ACTION,
        EventType.COMPLETE,
        "recovery.execution-boundary",
        ("request_id", "failure_id", "strategy", "success"),
        ("result",),
        "Recovery execution completion.",
    ),
    _definition(
        "RecoveryExecutionFailed",
        Category.ACTION,
        EventType.FAILURE,
        "recovery.execution-boundary",
        ("request_id", "failure_id", "strategy", "error"),
        (),
        "Recovery execution failure.",
    ),
    _definition(
        "OptimizationStarted",
        Category.ACTION,
        EventType.START,
        "optimizer",
        ("optimization_id",),
    ),
    _definition(
        "OptimizationCompleted",
        Category.ACTION,
        EventType.COMPLETE,
        "optimizer",
        ("optimization_id", "success"),
        ("changes", "metrics"),
    ),
    _definition(
        "OptimizationFailed",
        Category.ACTION,
        EventType.FAILURE,
        "optimizer",
        ("optimization_id", "error"),
    ),
    _definition(
        "OptimizationDecisionCreated",
        Category.ACTION,
        EventType.CREATED,
        "optimizer",
        ("decision_id", "action"),
        ("reason", "score"),
    ),
    _definition(
        "PolicyTuningStarted",
        Category.ACTION,
        EventType.START,
        "optimizer",
        ("tuning_id",),
    ),
    _definition(
        "PolicyTuningCompleted",
        Category.ACTION,
        EventType.COMPLETE,
        "optimizer",
        ("tuning_id", "success"),
        ("changes", "metrics"),
    ),
    _definition(
        "OptimizationUpdateRequested",
        Category.ACTION,
        EventType.START,
        "optimizer.update-boundary",
        ("request",),
    ),
    _definition(
        "OptimizationUpdateCompleted",
        Category.ACTION,
        EventType.COMPLETE,
        "optimizer.update-boundary",
        ("request", "result"),
    ),
    _definition(
        "OptimizationUpdateFailed",
        Category.ACTION,
        EventType.FAILURE,
        "optimizer.update-boundary",
        ("request", "result"),
    ),
    _definition(
        "PolicyUpdated",
        Category.ACTION,
        EventType.UPDATED,
        "optimizer.update-boundary",
        ("optimization_id", "request_id", "action", "target", "change"),
    ),
    _definition(
        "ContextUpdated",
        Category.RUNTIME,
        EventType.UPDATED,
        "optimizer.update-boundary",
        ("optimization_id", "request_id", "action", "target", "change"),
    ),
    _definition(
        "MemoryUpdated",
        Category.MEMORY,
        EventType.UPDATED,
        "optimizer.update-boundary",
        ("optimization_id", "request_id", "action", "target", "change"),
    ),
    _definition(
        "OptimizationEvidenceRecorded",
        Category.ACTION,
        EventType.CREATED,
        "optimizer.evidence-boundary",
        ("request_id", "optimization_id", "evidence_id", "material_changes"),
    ),
    _definition(
        "OptimizationEvidenceFailed",
        Category.ACTION,
        EventType.FAILURE,
        "optimizer.evidence-boundary",
        ("request_id", "optimization_id", "material_changes", "error"),
    ),
    _definition(
        "LearningClosedLoopStarted",
        Category.LEARNING,
        EventType.START,
        "learning.closed-loop",
        ("cycle_id", "result_id", "goal_id"),
    ),
    _definition(
        "LearningOptimizationStarted",
        Category.LEARNING,
        EventType.START,
        "learning.closed-loop",
        ("cycle_id",),
    ),
    _definition(
        "LearningClosedLoopCompleted",
        Category.LEARNING,
        EventType.COMPLETE,
        "learning.closed-loop",
        ("cycle_id", "result_id", "success", "status"),
        ("error_type", "error"),
    ),
    _definition(
        "LearningClosedLoopFailed",
        Category.LEARNING,
        EventType.FAILURE,
        "learning.closed-loop",
        ("cycle_id", "result_id", "success", "status"),
        (
            "error_type",
            "error",
            "evidence_error",
            "evidence_error_type",
            "evidence_failure_kind",
            "reconciliation_reason",
            "reconciles_terminal_status",
            "reconciles_terminal_event_id",
        ),
    ),
    _definition(
        "LearningClosedLoopEvidenceRecorded",
        Category.LEARNING,
        EventType.CREATED,
        "learning.closed-loop.evidence-boundary",
        ("cycle_id", "result_id", "evidence_id", "status", "success"),
        ("related_optimization_evidence_ids",),
    ),
    _definition(
        "LearningClosedLoopEvidenceFailed",
        Category.LEARNING,
        EventType.FAILURE,
        "learning.closed-loop.evidence-boundary",
        ("cycle_id", "result_id", "status", "error"),
    ),
    _definition(
        "DeploymentStarted",
        Category.COMPONENT,
        EventType.START,
        "deployment",
        ("deployment_id", "version"),
    ),
    _definition(
        "DeploymentCompleted",
        Category.COMPONENT,
        EventType.COMPLETE,
        "deployment",
        ("deployment_id", "version", "success"),
        ("target",),
    ),
    _definition(
        "DeploymentFailed",
        Category.COMPONENT,
        EventType.FAILURE,
        "deployment",
        ("deployment_id", "version", "error"),
    ),
    _definition(
        "RollbackStarted",
        Category.COMPONENT,
        EventType.START,
        "deployment",
        ("deployment_id", "version"),
    ),
    _definition(
        "RollbackCompleted",
        Category.COMPONENT,
        EventType.COMPLETE,
        "deployment",
        ("deployment_id", "version", "success"),
        ("target",),
    ),
)


def _version_key(version: str) -> tuple[int, int, int, str]:
    parts = version.split(".", 2)
    numbers: list[int] = []
    for part in parts[:3]:
        try:
            numbers.append(int(part))
        except ValueError:
            numbers.append(0)
    while len(numbers) < 3:
        numbers.append(0)
    suffix = parts[2] if len(parts) == 3 else ""
    return numbers[0], numbers[1], numbers[2], suffix
