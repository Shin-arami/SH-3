from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum, unique
from threading import Event as ThreadEvent
from threading import RLock, get_ident
from types import MappingProxyType
from typing import Any

from cognition.contracts import CognitiveLifecycleState, CognitiveResult, CognitiveResultStatus
from cognition.feedback import CognitiveFeedback, CognitiveFeedbackBridge, CognitiveFeedbackKind
from cognition.feedback_boundary import CognitiveFeedbackBoundary
from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.utils.logging import error
from infrastructure.event_bus import EventBus, EventPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from kernel.cognitive_learning_boundary import CognitiveLearningBoundary
from kernel.learning_closed_loop_evidence_boundary import LearningClosedLoopEvidenceBoundary
from kernel.learning_optimizer_boundary import LearningOptimizerBoundary
from kernel.optimizer_healing_boundary import OptimizerHealingBoundary
from kernel.recovery_execution_boundary import RecoveryExecutionBoundary
from kernel.recovery_strategy_boundary import RecoveryStrategyBoundary

__all__ = ["ClosedLoopStatus", "LearningClosedLoopCoordinator", "LearningClosedLoopReport"]


@unique
class ClosedLoopStatus(StrEnum):
    COMPLETED = "completed"
    RECOVERED = "recovered"
    FAILED = "failed"


def _map(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


@dataclass(frozen=True, slots=True)
class LearningClosedLoopReport:
    cycle_id: str
    result_id: str
    goal_id: str
    status: ClosedLoopStatus
    created_at: datetime
    correlation_id: str
    causation_id: str | None
    trace_id: str | None
    tenant_id: str | None
    learning_result: Mapping[str, Any] = field(default_factory=dict)
    optimization_result: Mapping[str, Any] | None = None
    healing_result: Any = None
    feedback: tuple[CognitiveFeedback, ...] = ()
    failure_detail: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in (("cycle_id", self.cycle_id), ("result_id", self.result_id), ("goal_id", self.goal_id), ("correlation_id", self.correlation_id)):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must not be empty")
        if not isinstance(self.status, ClosedLoopStatus):
            raise TypeError("status must be ClosedLoopStatus")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        for field_name, field_value in (("causation_id", self.causation_id), ("trace_id", self.trace_id), ("tenant_id", self.tenant_id)):
            if field_value is not None and (not isinstance(field_value, str) or not field_value):
                raise ValueError(f"{field_name} must be non-empty when provided")
        if not all(isinstance(item, CognitiveFeedback) for item in self.feedback):
            raise TypeError("feedback must contain CognitiveFeedback")
        object.__setattr__(self, "learning_result", _map(self.learning_result))
        object.__setattr__(self, "optimization_result", None if self.optimization_result is None else _map(self.optimization_result))

        if not isinstance(self.failure_detail, Mapping):
            raise TypeError("failure_detail must be a mapping")
        if any(
            not isinstance(key, str)
            or not key.strip()
            or not isinstance(value, str)
            for key, value in self.failure_detail.items()
        ):
            raise TypeError("failure_detail must contain string keys and values")
        object.__setattr__(
            self,
            "failure_detail",
            MappingProxyType(dict(self.failure_detail)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "result_id": self.result_id,
            "goal_id": self.goal_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "learning_result": dict(self.learning_result),
            "optimization_result": None if self.optimization_result is None else dict(self.optimization_result),
            "healing_result": self.healing_result,
            "feedback": [item.to_dict() for item in self.feedback],
            "failure_detail": dict(self.failure_detail),
        }


class LearningClosedLoopCoordinator:
    __slots__ = (
        "_closed_loop_evidence_boundary",
        "_cycle_failure_details",
        "_cycle_options",
        "_cycles",
        "_event_bus",
        "_event_publisher",
        "_feedback_boundary",
        "_feedback_bridge",
        "_goal_inflight",
        "_goal_lifecycle_states",
        "_goal_partial_counts",
        "_healing_boundary",
        "_inflight",
        "_learning_boundary",
        "_lock",
        "_max_partial_cycles",
        "_optimizer_boundary",
        "_recovery_execution_boundary",
        "_recovery_strategy_boundary",
        "_started",
        "kernel",
    )

    def __init__(
        self,
        kernel: Any,
        *,
        event_publisher: EventPublisher | None = None,
        learning_boundary: CognitiveLearningBoundary | None = None,
        optimizer_boundary: LearningOptimizerBoundary | None = None,
        healing_boundary: OptimizerHealingBoundary | None = None,
        recovery_strategy_boundary: RecoveryStrategyBoundary | None = None,
        recovery_execution_boundary: RecoveryExecutionBoundary | None = None,
        feedback_boundary: CognitiveFeedbackBoundary | None = None,
        closed_loop_evidence_boundary: LearningClosedLoopEvidenceBoundary | None = None,
        max_partial_cycles: int = 3,
    ) -> None:
        if kernel is None:
            raise TypeError("kernel must not be None")
        if isinstance(max_partial_cycles, bool) or not isinstance(
            max_partial_cycles, int
        ):
            raise TypeError("max_partial_cycles must be an integer")
        if max_partial_cycles < 1:
            raise ValueError("max_partial_cycles must be >= 1")
        if event_publisher is not None and not isinstance(event_publisher, EventPublisher):
            raise TypeError("event_publisher must be EventPublisher or None")
        self.kernel = kernel
        self._event_publisher = event_publisher
        self._event_bus: EventBus | None = None
        self._feedback_bridge = CognitiveFeedbackBridge(kernel.cognition, event_publisher)
        self._learning_boundary = learning_boundary or getattr(kernel, "cognitive_learning_boundary", None) or CognitiveLearningBoundary(kernel.learning_loop, event_publisher)
        self._optimizer_boundary = optimizer_boundary or getattr(kernel, "learning_optimizer_boundary", None) or LearningOptimizerBoundary(kernel.system_optimizer, event_publisher)
        self._healing_boundary = healing_boundary or getattr(kernel, "optimizer_healing_boundary", None) or OptimizerHealingBoundary(kernel.meta_controller.healer, event_publisher)
        self._recovery_strategy_boundary = recovery_strategy_boundary or getattr(kernel, "recovery_strategy_boundary", None) or RecoveryStrategyBoundary(kernel.meta_controller.healer, event_publisher)
        self._recovery_execution_boundary = recovery_execution_boundary or getattr(kernel, "recovery_execution_boundary", None) or RecoveryExecutionBoundary(kernel.meta_controller.healer, event_publisher)
        self._feedback_boundary = feedback_boundary or getattr(kernel, "feedback_boundary", None) or CognitiveFeedbackBoundary(kernel.cognition, event_publisher)
        existing_evidence_boundary = getattr(kernel, "learning_closed_loop_evidence_boundary", None)
        existing_evidence_store = getattr(
            getattr(kernel, "optimizer_evidence_boundary", None),
            "evidence_store",
            None,
        )
        self._closed_loop_evidence_boundary = (
            closed_loop_evidence_boundary
            or existing_evidence_boundary
            or LearningClosedLoopEvidenceBoundary(existing_evidence_store, event_publisher)
        )
        if not isinstance(self._learning_boundary, CognitiveLearningBoundary):
            raise TypeError("learning_boundary must be CognitiveLearningBoundary")
        if not isinstance(self._optimizer_boundary, LearningOptimizerBoundary):
            raise TypeError("optimizer_boundary must be LearningOptimizerBoundary")
        if not isinstance(self._healing_boundary, OptimizerHealingBoundary):
            raise TypeError("healing_boundary must be OptimizerHealingBoundary")
        if not isinstance(self._recovery_strategy_boundary, RecoveryStrategyBoundary):
            raise TypeError("recovery_strategy_boundary must be RecoveryStrategyBoundary")
        if not isinstance(self._recovery_execution_boundary, RecoveryExecutionBoundary):
            raise TypeError("recovery_execution_boundary must be RecoveryExecutionBoundary")
        if not isinstance(self._feedback_boundary, CognitiveFeedbackBoundary):
            raise TypeError("feedback_boundary must be CognitiveFeedbackBoundary")
        if not isinstance(self._closed_loop_evidence_boundary, LearningClosedLoopEvidenceBoundary):
            raise TypeError("closed_loop_evidence_boundary must be LearningClosedLoopEvidenceBoundary")
        self._lock = RLock()
        self._cycles: dict[str, LearningClosedLoopReport] = {}
        self._cycle_options: dict[str, tuple[bool, bool]] = {}
        self._inflight: dict[str, tuple[ThreadEvent, int]] = {}
        self._goal_inflight: dict[str, tuple[str, int]] = {}
        self._goal_lifecycle_states: dict[str, CognitiveLifecycleState] = {}
        self._started = False
        self._max_partial_cycles = max_partial_cycles
        self._goal_partial_counts: dict[str, int] = {}
        self._cycle_failure_details: dict[str, dict[str, str]] = {}
        self._configure()

    @property
    def event_publisher(self) -> EventPublisher | None:
        with self._lock:
            return self._event_publisher

    @property
    def learning_boundary(self) -> CognitiveLearningBoundary:
        return self._learning_boundary

    @property
    def optimizer_boundary(self) -> LearningOptimizerBoundary:
        return self._optimizer_boundary

    @property
    def healing_boundary(self) -> OptimizerHealingBoundary:
        return self._healing_boundary

    @property
    def feedback_boundary(self) -> CognitiveFeedbackBoundary:
        return self._feedback_boundary

    @property
    def recovery_strategy_boundary(self) -> RecoveryStrategyBoundary:
        return self._recovery_strategy_boundary

    @property
    def recovery_execution_boundary(self) -> RecoveryExecutionBoundary:
        return self._recovery_execution_boundary

    @property
    def started(self) -> bool:
        with self._lock:
            return self._started

    def set_event_publisher(self, publisher: EventPublisher | None) -> None:
        if publisher is not None and not isinstance(publisher, EventPublisher):
            raise TypeError("publisher must be EventPublisher or None")
        with self._lock:
            self._event_publisher = publisher
        self._feedback_bridge.set_event_publisher(publisher)
        self._learning_boundary.set_event_publisher(publisher)
        self._optimizer_boundary.set_event_publisher(publisher)
        self._healing_boundary.set_event_publisher(publisher)
        self._recovery_strategy_boundary.set_event_publisher(publisher)
        self._recovery_execution_boundary.set_event_publisher(publisher)
        self._feedback_boundary.set_event_publisher(publisher)
        self._closed_loop_evidence_boundary.set_event_publisher(publisher)
        self._configure()

    def _configure(self) -> None:
        publisher = self._event_publisher
        event_bus = getattr(publisher, "event_bus", None) if publisher is not None else None
        if event_bus is not None and not isinstance(event_bus, EventBus):
            event_bus = None
        if self._event_bus is event_bus:
            return
        if self._event_bus is not None:
            with suppress(KeyError):
                self._event_bus.unsubscribe("learning.closed-loop")
        self._event_bus = event_bus
        if event_bus is None:
            with self._lock:
                self._started = False
            return
        event_bus.subscribe(
            EventSubscription(
                subscriber_id="learning.closed-loop",
                handler=self._handle_cognition_result,
                event_name="CognitionResultRecorded",
                priority=50,
            ),
            replace=True,
        )
        with self._lock:
            self._started = True

    def records(self) -> tuple[LearningClosedLoopReport, ...]:
        with self._lock:
            return tuple(self._cycles.values())

    def get(self, cycle_id: str) -> LearningClosedLoopReport | None:
        with self._lock:
            return self._cycles.get(cycle_id)

    def run(
        self,
        result: CognitiveResult,
        *,
        context: EventPropagationContext | None = None,
        optimize: bool = True,
        recover: bool = True,
    ) -> LearningClosedLoopReport:
        if not isinstance(result, CognitiveResult):
            raise TypeError("result must be CognitiveResult")

        expected_state = {
            CognitiveResultStatus.SUCCESS: CognitiveLifecycleState.COMPLETED,
            CognitiveResultStatus.FAILURE: CognitiveLifecycleState.FAILED,
            CognitiveResultStatus.PARTIAL: CognitiveLifecycleState.ACTIVE,
        }[result.status]
        if result.lifecycle_state is not expected_state:
            raise ValueError(
                "result status and lifecycle_state are inconsistent: "
                f"status={result.status.value}, "
                f"lifecycle_state={result.lifecycle_state.value}"
            )

        cycle_id = f"learning-cycle:{result.result_id}"
        options = (optimize, recover)
        current_thread = get_ident()
        convergence_failure_detail: dict[str, str] | None = None
        next_partial_count = 0
        existing_report: LearningClosedLoopReport | None = None

        with self._lock:
            configured_options = self._cycle_options.get(cycle_id)
            if configured_options is not None and configured_options != options:
                raise ValueError(
                    f"closed-loop cycle options conflict for {cycle_id}: "
                    f"requested={options!r}, established={configured_options!r}"
                )

            existing = self._cycles.get(cycle_id)
            inflight = self._inflight.get(cycle_id)
            if inflight is not None:
                waiter, owner_thread = inflight
                if owner_thread == current_thread:
                    raise RuntimeError(
                        f"closed-loop cycle re-entry detected: {cycle_id}"
                    )
                leader = False
            elif existing is not None:
                existing_report = existing
                leader = False
            else:
                previous_state = self._goal_lifecycle_states.get(result.goal_id)
                if previous_state in (
                    CognitiveLifecycleState.COMPLETED,
                    CognitiveLifecycleState.FAILED,
                    CognitiveLifecycleState.TERMINATED,
                ):
                    raise ValueError(
                        "closed-loop goal is already in a terminal lifecycle state: "
                        f"goal_id={result.goal_id}, state={previous_state.value}"
                    )

                goal_inflight = self._goal_inflight.get(result.goal_id)
                if goal_inflight is not None:
                    active_cycle_id, owner_thread = goal_inflight
                    if owner_thread == current_thread:
                        raise RuntimeError(
                            "closed-loop goal re-entry detected: "
                            f"{result.goal_id} ({active_cycle_id})"
                        )
                    raise RuntimeError(
                        "closed-loop goal already has an in-flight cycle: "
                        f"{result.goal_id} ({active_cycle_id})"
                    )

                next_partial_count = self._goal_partial_counts.get(
                    result.goal_id,
                    0,
                )
                if result.status is CognitiveResultStatus.PARTIAL:
                    next_partial_count += 1
                    if next_partial_count >= self._max_partial_cycles:
                        convergence_error = (
                            f"maximum partial cycles reached for goal "
                            f"{result.goal_id}: "
                            f"{next_partial_count}/{self._max_partial_cycles}"
                        )
                        convergence_failure_detail = {
                            "failure_kind": "convergence_limit",
                            "convergence_error_type": (
                                "ClosedLoopConvergenceLimitError"
                            ),
                            "convergence_error": convergence_error,
                            "partial_cycles": str(next_partial_count),
                            "max_partial_cycles": str(self._max_partial_cycles),
                        }

                waiter = ThreadEvent()
                self._inflight[cycle_id] = (waiter, current_thread)
                self._goal_inflight[result.goal_id] = (cycle_id, current_thread)
                self._cycle_options[cycle_id] = options
                if convergence_failure_detail is not None:
                    self._cycle_failure_details[cycle_id] = (
                        convergence_failure_detail
                    )
                leader = True

        if existing_report is not None:
            self._retry_finalization(existing_report)
            return existing_report

        if not leader:
            waiter.wait()
            existing = self.get(cycle_id)
            if existing is None:
                raise RuntimeError(
                    f"closed-loop report not produced: {cycle_id}"
                )
            return existing

        try:
            report = self._run_cycle(
                result,
                cycle_id,
                context=context,
                optimize=optimize,
                recover=recover,
            )
            with self._lock:
                if result.status is CognitiveResultStatus.PARTIAL:
                    self._goal_partial_counts[result.goal_id] = (
                        next_partial_count
                    )
                self._goal_lifecycle_states[result.goal_id] = (
                    CognitiveLifecycleState.FAILED
                    if convergence_failure_detail is not None
                    or report.status is ClosedLoopStatus.FAILED
                    else result.lifecycle_state
                )
            return report
        finally:
            with self._lock:
                self._cycle_failure_details.pop(cycle_id, None)
                completion = self._inflight.pop(cycle_id, None)
                if completion is not None:
                    if cycle_id in self._cycles:
                        self._goal_lifecycle_states.setdefault(
                            result.goal_id,
                            result.lifecycle_state,
                        )
                    goal_inflight = self._goal_inflight.get(result.goal_id)
                    if (
                        goal_inflight is not None
                        and goal_inflight[0] == cycle_id
                    ):
                        self._goal_inflight.pop(result.goal_id, None)
                    if cycle_id not in self._cycles:
                        self._cycle_options.pop(cycle_id, None)
                    completion[0].set()

    def _retry_finalization(self, report: LearningClosedLoopReport) -> None:
        feedback_error = report.failure_detail.get("feedback_error")
        if feedback_error:
            aggregate_feedback = next(
                (
                    item
                    for item in reversed(report.feedback)
                    if item.kind is CognitiveFeedbackKind.CLOSED_LOOP
                ),
                None,
            )
            if aggregate_feedback is not None:
                feedback_context = EventPropagationContext.create(
                    correlation_id=aggregate_feedback.correlation_id,
                    causation_id=aggregate_feedback.causation_id,
                    trace_id=aggregate_feedback.trace_id,
                    tenant_id=aggregate_feedback.tenant_id,
                )
                try:
                    feedback_result = self._feedback_boundary.record(
                        aggregate_feedback,
                        context=feedback_context,
                        created_at=aggregate_feedback.created_at,
                    )
                    if not feedback_result.success:
                        error(
                            "Closed-loop feedback retry failed",
                            {
                                "cycle_id": report.cycle_id,
                                "error": feedback_result.error or feedback_error,
                            },
                        )
                except Exception as exc:
                    error(
                        "Closed-loop feedback retry raised an exception",
                        {"cycle_id": report.cycle_id, "error": str(exc)},
                    )

        evidence_result = self._closed_loop_evidence_boundary.get(report.cycle_id)
        if evidence_result is None or not evidence_result.recorded:
            evidence_context = EventPropagationContext.create(
                correlation_id=report.correlation_id,
                causation_id=report.causation_id,
                trace_id=report.trace_id,
                tenant_id=report.tenant_id,
            )
            try:
                retried_evidence = self._closed_loop_evidence_boundary.record(
                    report,
                    context=evidence_context,
                    created_at=report.created_at,
                )
                if not retried_evidence.recorded:
                    error(
                        "Closed-loop evidence retry failed",
                        {
                            "cycle_id": report.cycle_id,
                            "error": retried_evidence.error or "evidence recording failed",
                        },
                    )
            except Exception as exc:
                error(
                    "Closed-loop evidence retry raised an exception",
                    {"cycle_id": report.cycle_id, "error": str(exc)},
                )

    def _run_cycle(
        self,
        result: CognitiveResult,
        cycle_id: str,
        *,
        context: EventPropagationContext | None,
        optimize: bool,
        recover: bool,
    ) -> LearningClosedLoopReport:
        propagation = context or EventPropagationContext.create(
            correlation_id=result.correlation_id,
            causation_id=result.result_id,
            trace_id=result.trace_id,
            tenant_id=result.tenant_id,
        )
        now = result.created_at.astimezone(UTC)
        feedback: list[CognitiveFeedback] = []
        learning_result: dict[str, Any] = {}
        optimization_result: dict[str, Any] | None = None
        healing_result: Any = None
        status = ClosedLoopStatus.COMPLETED
        failure_detail: dict[str, str] = {}
        try:
            propagation = self._publish(
                "LearningClosedLoopStarted",
                EventType.START,
                {
                    "cycle_id": cycle_id,
                    "result_id": result.result_id,
                    "goal_id": result.goal_id
                },
                    propagation
            )
            learning_value = self._learning_boundary.record(
                result,
                context=propagation,
                created_at=now
            )
            propagation = learning_value.propagation_context
            if not learning_value.success:
                raise RuntimeError(learning_value.error or f"cognitive learning failed: {learning_value.request_id}")
            learning_result = dict(learning_value.learning)
            score = float(learning_result.get("score", 0.0))
            if result.status is CognitiveResultStatus.FAILURE:
                if recover:
                    healing_result = self._recover("cognition", cycle_id, result, propagation)
                    status = ClosedLoopStatus.RECOVERED
                else:
                    status = ClosedLoopStatus.FAILED
            learning_success = result.status is CognitiveResultStatus.SUCCESS and bool(learning_result)
            feedback.append(CognitiveFeedback.create(
                cycle_id=cycle_id, goal_id=result.goal_id, kind=CognitiveFeedbackKind.LEARNING,
                source_id=learning_value.loop_id, success=learning_success,
                score=max(0.0, min(1.0, score)), reason="learning cycle evaluated cognitive result",
                correlation_id=propagation.correlation_id, causation_id=propagation.causation_id,
                trace_id=propagation.trace_id, tenant_id=propagation.tenant_id, created_at=now,
                metadata={"result_id": result.result_id, "memory_key": learning_result.get("memory_key")},
            ))
            if optimize:
                propagation = self._publish(
                    "LearningOptimizationStarted",
                    EventType.START,
                    {"cycle_id": cycle_id},
                    propagation
                )
                optimization = self._optimizer_boundary.request(learning_result, context=propagation, created_at=now)
                propagation = optimization.propagation_context
                optimization_result = dict(optimization.optimization)
                execution = optimization.optimization.get("execution", ())
                optimization_success = optimization.success
                if not optimization_success:
                    status = ClosedLoopStatus.RECOVERED if recover else ClosedLoopStatus.FAILED
                    if recover:
                        healing = self._healing_boundary.request(optimization, context=propagation, created_at=now)
                        propagation = healing.propagation_context
                        healing_result = {
                            "success": healing.success,
                            "status": "recovered" if healing.success else "failed",
                            "result": dict(healing.healing),
                            "failure_id": healing.failure_id,
                            "error": healing.error,
                        }
                        if not healing.success:
                            status = ClosedLoopStatus.FAILED
                feedback.append(CognitiveFeedback.create(
                    cycle_id=cycle_id, goal_id=result.goal_id, kind=CognitiveFeedbackKind.OPTIMIZATION,
                    source_id=optimization.optimizer_id, success=optimization_success,
                    score=1.0 if optimization_success else 0.0, reason="optimizer evaluated learning outcome",
                    correlation_id=propagation.correlation_id, causation_id=propagation.causation_id,
                    trace_id=propagation.trace_id, tenant_id=propagation.tenant_id, created_at=now,
                    metadata={"execution": execution},
                ))
            if healing_result is not None and not any(item.kind is CognitiveFeedbackKind.SELF_HEALING for item in feedback):
                healed = healing_result.get("status") == "recovered" if isinstance(healing_result, Mapping) else False
                feedback.append(CognitiveFeedback.create(
                    cycle_id=cycle_id, goal_id=result.goal_id, kind=CognitiveFeedbackKind.SELF_HEALING,
                    source_id="self-healing", success=healed,
                    score=1.0 if healed else 0.0, reason="self-healing processed closed loop",
                    correlation_id=propagation.correlation_id, causation_id=propagation.causation_id,
                    trace_id=propagation.trace_id, tenant_id=propagation.tenant_id, created_at=now,
                    metadata={"result_id": result.result_id},
                ))
        except Exception as exc:
            healing_error: Exception | None = None
            if recover:
                try:
                    healing_result = self._recover("closed_loop", cycle_id, result, propagation, error=exc)
                except Exception as recovery_exc:
                    healing_error = recovery_exc
                    healing_result = None
            status = ClosedLoopStatus.RECOVERED if healing_result is not None else ClosedLoopStatus.FAILED
            feedback.append(CognitiveFeedback.create(
                cycle_id=cycle_id, goal_id=result.goal_id, kind=CognitiveFeedbackKind.SELF_HEALING,
                source_id="self-healing", success=healing_result is not None,
                score=1.0 if healing_result is not None else 0.0, reason=f"closed loop failure: {type(exc).__name__}: {exc}",
                correlation_id=propagation.correlation_id, causation_id=propagation.causation_id,
                trace_id=propagation.trace_id, tenant_id=propagation.tenant_id, created_at=now,
                metadata={"error_type": type(exc).__name__, "recovery_error": None if healing_error is None else str(healing_error)},
            ))
            failure_detail = {"error_type": type(exc).__name__, "error": str(exc)}
        with self._lock:
            convergence_failure_detail = self._cycle_failure_details.get(cycle_id)

        if convergence_failure_detail is not None:
            status = ClosedLoopStatus.FAILED
            failure_detail.setdefault(
                "error_type",
                convergence_failure_detail["convergence_error_type"],
            )
            failure_detail.setdefault(
                "error",
                convergence_failure_detail["convergence_error"],
            )
            failure_detail.update(convergence_failure_detail)

        with self._lock:
            convergence_failure_detail = self._cycle_failure_details.get(
                cycle_id
            )

        if convergence_failure_detail is not None:
            status = ClosedLoopStatus.FAILED
            failure_detail.setdefault(
                "error_type",
                convergence_failure_detail["convergence_error_type"],
            )
            failure_detail.setdefault(
                "error",
                convergence_failure_detail["convergence_error"],
            )
            failure_detail.update(convergence_failure_detail)

        aggregate_success = status is not ClosedLoopStatus.FAILED and all(item.success for item in feedback if item.kind is not CognitiveFeedbackKind.SELF_HEALING or healing_result is not None)
        aggregate_metadata: dict[str, Any] = {
            "result_id": result.result_id,
            "status": status.value,
            "status_scope": "pre_feedback_recording",
        }
        if failure_detail:
            aggregate_metadata["failure_detail"] = dict(failure_detail)

        aggregate_feedback = CognitiveFeedback.create(
            cycle_id=cycle_id, goal_id=result.goal_id, kind=CognitiveFeedbackKind.CLOSED_LOOP,
            source_id=cycle_id, success=aggregate_success,
            score=round(sum(item.score for item in feedback) / len(feedback), 3) if feedback else 0.0,
            reason="closed loop feedback returned to cognition",
            correlation_id=propagation.correlation_id, causation_id=propagation.causation_id,
            trace_id=propagation.trace_id, tenant_id=propagation.tenant_id, created_at=now,
            metadata=aggregate_metadata,
        )
        feedback.append(aggregate_feedback)
        try:
            feedback_result = self._feedback_boundary.record(
                aggregate_feedback,
                context=propagation,
                created_at=now,
            )
        except Exception as exc:
            with self._lock:
                convergence_failure_detail = self._cycle_failure_details.get(
                    cycle_id
                )
            if convergence_failure_detail is not None:
                status = ClosedLoopStatus.FAILED
                failure_detail.setdefault(
                    "error_type",
                    convergence_failure_detail["convergence_error_type"],
                )
                failure_detail.setdefault(
                    "error",
                    convergence_failure_detail["convergence_error"],
                )

            status = ClosedLoopStatus.FAILED
            failure_detail.setdefault("error_type", type(exc).__name__)
            failure_detail.setdefault("error", str(exc))
            failure_detail["feedback_error_type"] = type(exc).__name__
            failure_detail["feedback_error"] = str(exc)

        else:
            propagation = feedback_result.propagation_context
            if not feedback_result.success:
                status = ClosedLoopStatus.FAILED
                feedback_error = (
                    feedback_result.error
                    or "closed-loop feedback recording failed"
                )
                failure_detail.setdefault(
                    "error_type",
                    "CognitiveFeedbackRecordingError",
                )
                failure_detail.setdefault("error", feedback_error)
                failure_detail["feedback_error_type"] = (
                    "CognitiveFeedbackRecordingError"
                )
                failure_detail["feedback_error"] = feedback_error
        terminal_event_name = (
            "LearningClosedLoopFailed"
            if status is ClosedLoopStatus.FAILED
            else "LearningClosedLoopCompleted"
        )
        terminal_event_type = (
            EventType.FAILURE
            if status is ClosedLoopStatus.FAILED
            else EventType.COMPLETE
        )
        terminal_payload: dict[str, Any] = {
            "cycle_id": cycle_id,
            "result_id": result.result_id,
            "success": status is not ClosedLoopStatus.FAILED,
            "status": status.value,
        }
        terminal_payload.update(failure_detail)
        propagation = self._publish(
            terminal_event_name,
            terminal_event_type,
            terminal_payload,
            propagation,
        )
        report = LearningClosedLoopReport(
            cycle_id=cycle_id,
            result_id=result.result_id,
            goal_id=result.goal_id,
            status=status,
            created_at=now,
            correlation_id=propagation.correlation_id,
            causation_id=propagation.causation_id,
            trace_id=propagation.trace_id,
            tenant_id=propagation.tenant_id,
            learning_result=learning_result,
            optimization_result=optimization_result,
            healing_result=healing_result,
            feedback=tuple(feedback),
            failure_detail=failure_detail,
        )
        with self._lock:
            self._cycles[cycle_id] = report
        evidence_result = self._closed_loop_evidence_boundary.record(
            report,
            context=propagation,
            created_at=now,
        )
        if evidence_result.recorded:
            return report

        error(
            "Learning closed-loop evidence was not recorded; retrying once",
            {"cycle_id": cycle_id, "error": evidence_result.error},
        )
        retry_result = self._closed_loop_evidence_boundary.record(
            report,
            context=propagation,
            created_at=now,
        )
        if retry_result.recorded:
            return report

        evidence_error = (
            retry_result.error
            or evidence_result.error
            or "closed-loop evidence persistence failed"
        )
        failure_detail = dict(report.failure_detail)
        failure_detail.setdefault(
            "error_type",
            "ClosedLoopEvidencePersistenceError",
        )
        failure_detail.setdefault("error", evidence_error)
        failure_detail["evidence_error_type"] = (
            "ClosedLoopEvidencePersistenceError"
        )
        failure_detail["evidence_error"] = evidence_error
        failure_detail.setdefault(
            "evidence_failure_kind",
            "evidence_persistence",
        )
        failure_payload: dict[str, Any] = {
            "cycle_id": cycle_id,
            "result_id": result.result_id,
            "success": False,
            "status": ClosedLoopStatus.FAILED.value,
        }
        failure_payload.update(failure_detail)
        failure_payload["reconciliation_reason"] = "evidence_persistence"
        failure_payload["reconciles_terminal_status"] = report.status.value
        if propagation.causation_id is not None:
            failure_payload["reconciles_terminal_event_id"] = (
                propagation.causation_id
            )
        failure_context = self._publish(
            "LearningClosedLoopFailed",
            EventType.FAILURE,
            failure_payload,
            propagation,
        )
        failed_report = replace(
            report,
            status=ClosedLoopStatus.FAILED,
            causation_id=failure_context.causation_id,
            failure_detail=failure_detail,
        )
        with self._lock:
            self._cycles[cycle_id] = failed_report

        final_evidence_result = self._closed_loop_evidence_boundary.record(
            failed_report,
            context=failure_context,
            created_at=now,
        )
        if not final_evidence_result.recorded:
            error(
                "Failed closed-loop report evidence remains pending",
                {
                    "cycle_id": cycle_id,
                    "error": final_evidence_result.error or evidence_error,
                },
            )
        return failed_report

    def _handle_cognition_result(self, event: Event) -> None:
        payload = event.payload.get("result")
        if not isinstance(payload, Mapping):
            return
        result = self._result_from_dict(payload)
        if result is None:
            return
        try:
            self.run(result, context=EventPropagationContext.from_event(event))
        except Exception as exc:
            error("Learning closed loop event handling failed", {"result_id": result.result_id, "error": str(exc)})

    @staticmethod
    def _result_from_dict(data: Mapping[str, Any]) -> CognitiveResult | None:
        try:
            output = data.get("output")
            if not isinstance(output, Mapping):
                return None
            goal_data = output.get("goal")
            if not isinstance(goal_data, Mapping):
                return None
            from cognition.contracts import CognitiveGoal, CognitiveLifecycleState
            goal = CognitiveGoal.create(
                str(goal_data["intent"]), owner=str(goal_data["owner"]), goal_type=str(goal_data["goal_type"]),
                version=str(goal_data["version"]), created_at=datetime.fromisoformat(str(goal_data["created_at"])),
                lifecycle_state=CognitiveLifecycleState(str(goal_data["lifecycle_state"])), success_criteria=tuple(goal_data.get("success_criteria", ())),
                constraints=goal_data.get("constraints", {}), priority=float(goal_data.get("priority", 0.0)), time_horizon=goal_data.get("time_horizon"),
                goal_id=str(goal_data["goal_id"]), correlation_id=str(goal_data["correlation_id"]), causation_id=goal_data.get("causation_id"),
                trace_id=goal_data.get("trace_id"), tenant_id=goal_data.get("tenant_id"), metadata=goal_data.get("metadata", {}),
            )
            return CognitiveResult.create(
                goal, status=CognitiveResultStatus(str(data["status"])), output=output,
                result_type=str(data["result_type"]), owner=str(data["owner"]), version=str(data["version"]),
                created_at=datetime.fromisoformat(str(data["created_at"])),
                lifecycle_state=CognitiveLifecycleState(str(data["lifecycle_state"])), error_type=data.get("error_type"),
                error_message=data.get("error_message"), correlation_id=str(data["correlation_id"]), causation_id=data.get("causation_id"),
                trace_id=data.get("trace_id"), tenant_id=data.get("tenant_id"), metadata=data.get("metadata", {}), result_id=str(data["result_id"]),
            )
        except Exception:
            return None

    def _recover(
        self,
        source: str,
        cycle_id: str,
        result: CognitiveResult,
        propagation: EventPropagationContext,
        *,
        error: Exception | None = None,
    ) -> Any:
        exc = error or RuntimeError(f"{source} cycle failure for {result.result_id}")
        self.kernel.meta_controller.healer.set_propagation_context(propagation)
        snapshot = self.kernel.meta_controller.healer.detect(exc, {"source": source, "cycle_id": cycle_id, "result_id": result.result_id})
        strategy = self._recovery_strategy_boundary.request(
            snapshot,
            context=self.kernel.meta_controller.healer.propagation_context or propagation,
            created_at=result.created_at,
        )
        execution = self._recovery_execution_boundary.request(
            strategy,
            snapshot,
            context=strategy.propagation_context,
            created_at=result.created_at,
        )
        self.kernel.meta_controller.healer.set_propagation_context(execution.propagation_context)
        if not execution.success:
            raise RuntimeError(execution.error or "recovery execution failed")
        return {
            "success": True,
            "status": "recovered",
            "result": execution.result,
            "failure_id": snapshot.trace_id,
            "strategy": execution.strategy,
            "execution_id": execution.request_id,
        }

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
                producer="learning.closed-loop",
                payload=payload,
                category=Category.LEARNING if event_name.startswith("Learning") or event_name == "CognitiveFeedbackRecorded" else Category.ACTION,
                event_type=event_type,
                correlation_id=context.correlation_id,
                causation_id=context.causation_id,
                trace_id=context.trace_id,
                tenant_id=context.tenant_id,
            )
            publisher.publish(event)
            return context.next(event.metadata.event_id)
        except Exception as exc:
            error("Closed loop event publication failed", {"event_name": event_name, "error": str(exc)})
            return context
