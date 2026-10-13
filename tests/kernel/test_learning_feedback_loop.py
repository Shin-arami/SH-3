from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime

import pytest

from cognition.contracts import (
    CognitiveGoal,
    CognitiveLifecycleState,
    CognitiveResult,
    CognitiveResultStatus,
)
from cognition.feedback import CognitiveFeedback, CognitiveFeedbackKind
from cognition.feedback_boundary import (
    CognitiveFeedbackBoundary,
    CognitiveFeedbackResult,
)
from infrastructure.event_bus import EventBus, EventBusPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from kernel.core import SH3Kernel
from kernel.learning_feedback_loop import (
    ClosedLoopStatus,
    LearningClosedLoopCoordinator,
    LearningClosedLoopReport,
)

NOW = datetime(2026, 10, 5, 0, 0, tzinfo=UTC)


def _result(
    status: CognitiveResultStatus = CognitiveResultStatus.SUCCESS,
    *,
    result_id: str | None = None,
) -> CognitiveResult:
    goal = CognitiveGoal.create(
        "prepare release",
        created_at=NOW,
        correlation_id="corr-phase3",
        trace_id="trace-phase3",
    )
    lifecycle_state = {
        CognitiveResultStatus.SUCCESS: CognitiveLifecycleState.COMPLETED,
        CognitiveResultStatus.FAILURE: CognitiveLifecycleState.FAILED,
        CognitiveResultStatus.PARTIAL: CognitiveLifecycleState.ACTIVE,
    }[status]
    return CognitiveResult.create(
        goal,
        status=status,
        lifecycle_state=lifecycle_state,
        created_at=NOW,
        error_type="RuntimeError" if status is CognitiveResultStatus.FAILURE else None,
        error_message="phase3 failure" if status is CognitiveResultStatus.FAILURE else None,
        output={
            "goal": goal.to_dict(),
            "plan": {"plan_id": "plan:phase3", "steps": ["prepare release"]},
            "decision": {"decision_id": "decision:phase3", "selected_option": "prepare release"},
        },
        result_id=result_id or (
            "result:phase3"
            if status is CognitiveResultStatus.SUCCESS
            else "result:phase3-failure"
            if status is CognitiveResultStatus.FAILURE
            else "result:phase3-partial"
        ),
    )


def test_closed_loop_runs_learning_optimizer_and_returns_feedback() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    bus.subscribe(EventSubscription(subscriber_id="phase3-audit", handler=events.append, priority=-200), replace=True)
    kernel = SH3Kernel(event_publisher=publisher)
    result = _result()

    report = kernel.learning_feedback_loop.run(result)

    assert report.status is ClosedLoopStatus.COMPLETED
    assert report.learning_result["score"] == 0.65
    assert report.optimization_result is not None
    assert report.feedback[-1].kind.value == "closed_loop"
    assert kernel.cognition.feedback_records()
    names = [event.name for event in events]
    assert "LearningClosedLoopStarted" in names
    assert "LearningResultRecorded" in names
    assert "OptimizationCompleted" in names
    assert "CognitiveFeedbackRecorded" in names


def test_closed_loop_is_idempotent_for_same_result() -> None:
    kernel = SH3Kernel()
    result = _result()
    first = kernel.learning_feedback_loop.run(result, optimize=False)
    second = kernel.learning_feedback_loop.run(result, optimize=False)
    assert first is second
    assert kernel.learning_feedback_loop.records() == (first,)


def test_terminal_state_replay_keeps_report_event_and_evidence_consistent() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    bus.subscribe(
        EventSubscription(
            subscriber_id="terminal-state-replay-audit",
            handler=events.append,
            priority=-100,
        )
    )
    kernel = SH3Kernel(event_publisher=publisher)
    result = _result(result_id="result:terminal-replay-safety")

    first = kernel.learning_feedback_loop.run(result, optimize=False)
    initial_terminal_count = sum(
        event.name in {"LearningClosedLoopCompleted", "LearningClosedLoopFailed"}
        and event.payload.get("cycle_id") == first.cycle_id
        for event in events
    )
    initial_evidence_event_count = sum(
        event.name == "LearningClosedLoopEvidenceRecorded"
        and event.payload.get("cycle_id") == first.cycle_id
        for event in events
    )
    second = kernel.learning_feedback_loop.run(result, optimize=False)

    assert second is first
    assert len(kernel.learning_feedback_loop.records()) == 1
    terminal_events = tuple(
        event
        for event in events
        if event.name in {"LearningClosedLoopCompleted", "LearningClosedLoopFailed"}
        and event.payload.get("cycle_id") == first.cycle_id
    )
    evidence_events = tuple(
        event
        for event in events
        if event.name == "LearningClosedLoopEvidenceRecorded"
        and event.payload.get("cycle_id") == first.cycle_id
    )
    assert initial_terminal_count == len(terminal_events) == 1
    assert initial_evidence_event_count == len(evidence_events) == 1
    assert terminal_events[0].payload["status"] == first.status.value
    assert terminal_events[0].payload["success"] is (
        first.status is not ClosedLoopStatus.FAILED
    )

    outcome = kernel.learning_closed_loop_evidence_boundary.get(first.cycle_id)
    assert outcome is not None and outcome.recorded and outcome.evidence is not None
    evidence = outcome.evidence
    assert evidence.payload["status"] == first.status.value
    assert evidence.payload["cycle_success"] is (
        first.status is not ClosedLoopStatus.FAILED
    )
    assert evidence.payload["fully_successful"] is (
        first.status is ClosedLoopStatus.COMPLETED
    )
    assert evidence.verify()
    assert sum(
        record.kind == "learning.closed_loop"
        and record.payload.get("cycle_id") == first.cycle_id
        for record in kernel.learning_closed_loop_evidence_boundary.evidence_store.records()
    ) == 1


def test_closed_loop_without_optimization_preserves_learning_feedback() -> None:
    kernel = SH3Kernel()
    report = kernel.learning_feedback_loop.run(_result(), optimize=False)
    assert report.status is ClosedLoopStatus.COMPLETED
    assert report.optimization_result is None
    assert any(item.kind.value == "learning" for item in report.feedback)
    assert any(item.kind.value == "closed_loop" for item in report.feedback)


def test_closed_loop_failed_cognition_triggers_self_healing() -> None:
    kernel = SH3Kernel()
    report = kernel.learning_feedback_loop.run(_result(CognitiveResultStatus.FAILURE), optimize=False, recover=True)
    assert report.status is ClosedLoopStatus.RECOVERED
    assert report.healing_result is not None
    assert any(item.kind.value == "self_healing" and item.success for item in report.feedback)
    assert kernel.cognition.latest_feedback() is not None


def test_closed_loop_failure_without_recovery_is_failed() -> None:
    kernel = SH3Kernel()
    report = kernel.learning_feedback_loop.run(_result(CognitiveResultStatus.FAILURE), optimize=False, recover=False)
    assert report.status is ClosedLoopStatus.FAILED
    assert report.healing_result is None
    assert report.feedback[-1].success is False


def test_closed_loop_uses_supplied_propagation_context() -> None:
    kernel = SH3Kernel()
    result = _result()
    context = EventPropagationContext.create(
        correlation_id="corr-custom",
        trace_id="trace-custom",
        tenant_id="tenant-custom",
        causation_id="cause-custom",
    )
    report = kernel.learning_feedback_loop.run(result, context=context, optimize=False)
    assert report.correlation_id == "corr-custom"
    assert report.trace_id == "trace-custom"
    assert report.tenant_id == "tenant-custom"


def test_closed_loop_can_start_automatically_from_cognition_event() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    kernel = SH3Kernel(event_publisher=publisher)
    result = _result()
    publisher.publish(
        Event.create(
            event_name="CognitionResultRecorded",
            producer="test",
            payload={"result": result.to_dict()},
            correlation_id=result.correlation_id,
            trace_id=result.trace_id,
        )
    )
    assert kernel.learning_feedback_loop.records()
    assert kernel.cognition.feedback_records()


def test_closed_loop_report_is_immutable() -> None:
    kernel = SH3Kernel()
    report = kernel.learning_feedback_loop.run(_result(), optimize=False)
    assert report.learning_result
    with suppress(AttributeError):
        report.cycle_id = "changed"  # type: ignore[misc]


def test_closed_loop_feedback_rejection_marks_terminal_event_failed() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    bus.subscribe(
        EventSubscription(
            subscriber_id="phase3-feedback-failure-audit",
            handler=events.append,
            priority=-200,
        ),
        replace=True,
    )
    kernel = SH3Kernel(event_publisher=publisher)

    class RejectingFeedbackBoundary(CognitiveFeedbackBoundary):
        def record(
            self,
            feedback: CognitiveFeedback,
            *,
            context: EventPropagationContext,
            created_at: datetime | None = None,
        ) -> CognitiveFeedbackResult:
            if feedback.kind is CognitiveFeedbackKind.CLOSED_LOOP:
                return CognitiveFeedbackResult(
                    request_id=f"rejected:{feedback.feedback_id}",
                    feedback_id=feedback.feedback_id,
                    success=False,
                    created_at=created_at or feedback.created_at,
                    correlation_id=context.correlation_id,
                    causation_id=context.causation_id,
                    trace_id=context.trace_id,
                    tenant_id=context.tenant_id,
                    error="injected feedback rejection",
                )
            return super().record(
                feedback,
                context=context,
                created_at=created_at,
            )

    feedback_boundary = RejectingFeedbackBoundary(
        kernel.cognition,
        publisher,
    )
    coordinator = LearningClosedLoopCoordinator(
        kernel,
        event_publisher=publisher,
        feedback_boundary=feedback_boundary,
    )

    report = coordinator.run(_result(), optimize=False)

    assert report.status is ClosedLoopStatus.FAILED
    assert report.feedback[-1].metadata["status"] == "completed"
    assert (
        report.feedback[-1].metadata["status_scope"]
        == "pre_feedback_recording"
    )

    failed_events = [
        event
        for event in events
        if event.name == "LearningClosedLoopFailed"
    ]
    assert failed_events
    assert failed_events[-1].payload["success"] is False
    assert (
        failed_events[-1].payload["feedback_error_type"]
        == "CognitiveFeedbackRecordingError"
    )
    assert (
        failed_events[-1].payload["feedback_error"]
        == "injected feedback rejection"
    )
    evidence_result = kernel.learning_closed_loop_evidence_boundary.get(
        report.cycle_id
    )
    assert evidence_result is not None
    assert evidence_result.recorded is True
    assert evidence_result.evidence is not None
    assert evidence_result.evidence.payload["status"] == ClosedLoopStatus.FAILED.value
    assert (
        evidence_result.evidence.payload["failure_detail"]["feedback_error"]
        == "injected feedback rejection"
    )


def test_feedback_finalization_retry_does_not_reexecute_cycle() -> None:
    class FailOnceFeedbackBoundary(CognitiveFeedbackBoundary):
        calls = 0

        def record(
            self,
            feedback: CognitiveFeedback,
            *,
            context: EventPropagationContext,
            created_at: datetime | None = None,
        ) -> CognitiveFeedbackResult:
            self.calls += 1
            if (
                feedback.kind is CognitiveFeedbackKind.CLOSED_LOOP
                and self.calls == 1
            ):
                return CognitiveFeedbackResult(
                    request_id=f"rejected:{feedback.feedback_id}",
                    feedback_id=feedback.feedback_id,
                    success=False,
                    created_at=created_at or feedback.created_at,
                    correlation_id=context.correlation_id,
                    causation_id=context.causation_id,
                    trace_id=context.trace_id,
                    tenant_id=context.tenant_id,
                    error="injected one-time feedback failure",
                )
            return super().record(
                feedback,
                context=context,
                created_at=created_at,
            )

    kernel = SH3Kernel()
    feedback_boundary = FailOnceFeedbackBoundary(kernel.cognition)
    coordinator = LearningClosedLoopCoordinator(
        kernel,
        feedback_boundary=feedback_boundary,
    )
    result = _result(result_id="result:feedback-finalization-retry")

    first = coordinator.run(result, optimize=False)
    assert first.status is ClosedLoopStatus.FAILED
    assert first.failure_detail["feedback_error"] == "injected one-time feedback failure"

    second = coordinator.run(result, optimize=False)

    assert second is first
    assert feedback_boundary.calls == 2
    assert len(coordinator.records()) == 1
    assert len(feedback_boundary.records()) == 1
    stored_evidence = kernel.learning_closed_loop_evidence_boundary.get(
        first.cycle_id
    )
    assert stored_evidence is not None and stored_evidence.recorded
    assert stored_evidence.evidence is not None
    assert stored_evidence.evidence.payload["status"] == ClosedLoopStatus.FAILED.value
    assert (
        stored_evidence.evidence.payload["failure_detail"]["feedback_error"]
        == "injected one-time feedback failure"
    )


def test_closed_loop_rejects_conflicting_options_for_same_result() -> None:
    kernel = SH3Kernel()
    coordinator = kernel.learning_feedback_loop
    result = _result()

    coordinator.run(result, optimize=False, recover=True)

    with pytest.raises(ValueError, match="options conflict"):
        coordinator.run(result, optimize=True, recover=True)


def test_closed_loop_reentrant_cycle_fails_without_deadlock() -> None:
    class ReentrantCoordinator(LearningClosedLoopCoordinator):
        def _run_cycle(
            self,
            result: CognitiveResult,
            cycle_id: str,
            *,
            context: EventPropagationContext | None,
            optimize: bool,
            recover: bool,
        ) -> LearningClosedLoopReport:
            return self.run(
                result,
                context=context,
                optimize=optimize,
                recover=recover,
            )

    coordinator = ReentrantCoordinator(SH3Kernel())
    result = _result()

    with pytest.raises(RuntimeError, match="re-entry detected"):
        coordinator.run(result, optimize=False)

    assert coordinator.records() == ()


def test_closed_loop_rejects_inconsistent_result_lifecycle() -> None:
    from dataclasses import replace

    kernel = SH3Kernel()
    result = _result()

    inconsistent = replace(
        result,
        lifecycle_state=CognitiveLifecycleState.ACTIVE,
    )

    with pytest.raises(
        ValueError,
        match="result status and lifecycle_state are inconsistent",
    ):
        kernel.learning_feedback_loop.run(inconsistent)

    assert kernel.learning_feedback_loop.records() == ()


def test_closed_loop_allows_partial_result_to_converge_to_success() -> None:
    kernel = SH3Kernel()
    coordinator = kernel.learning_feedback_loop

    partial = _result(
        CognitiveResultStatus.PARTIAL,
        result_id="result:phase3-partial",
    )
    partial_report = coordinator.run(partial, optimize=False)
    assert partial_report.status is ClosedLoopStatus.COMPLETED

    completed = _result(
        CognitiveResultStatus.SUCCESS,
        result_id="result:phase3-completed",
    )
    completed_report = coordinator.run(completed, optimize=False)

    assert completed_report.status is ClosedLoopStatus.COMPLETED
    assert completed_report.goal_id == partial_report.goal_id
    assert len(coordinator.records()) == 2


def test_closed_loop_rejects_new_result_after_terminal_goal_state() -> None:
    kernel = SH3Kernel()
    coordinator = kernel.learning_feedback_loop

    first = _result(
        CognitiveResultStatus.SUCCESS,
        result_id="result:phase3-terminal",
    )
    coordinator.run(first, optimize=False)

    duplicate_goal_result = _result(
        CognitiveResultStatus.SUCCESS,
        result_id="result:phase3-terminal-replay",
    )

    with pytest.raises(ValueError, match="terminal lifecycle state"):
        coordinator.run(duplicate_goal_result, optimize=False)

    assert len(coordinator.records()) == 1


def test_partial_cycle_limit_fails_and_records_reason() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    bus.subscribe(
        EventSubscription(
            subscriber_id="partial-convergence-audit",
            handler=events.append,
            priority=-200,
        ),
        replace=True,
    )

    kernel = SH3Kernel(event_publisher=publisher)
    coordinator = LearningClosedLoopCoordinator(
        kernel,
        event_publisher=publisher,
        max_partial_cycles=2,
    )

    first = _result(
        CognitiveResultStatus.PARTIAL,
        result_id="result:partial-limit-1",
    )
    first_report = coordinator.run(first, optimize=False)
    assert first_report.status is ClosedLoopStatus.COMPLETED

    second = _result(
        CognitiveResultStatus.PARTIAL,
        result_id="result:partial-limit-2",
    )
    report = coordinator.run(second, optimize=False)

    assert report.status is ClosedLoopStatus.FAILED
    assert report.failure_detail["failure_kind"] == "convergence_limit"
    assert report.failure_detail["partial_cycles"] == "2"
    assert report.failure_detail["max_partial_cycles"] == "2"

    failed_events = [
        event
        for event in events
        if event.name == "LearningClosedLoopFailed"
        and event.payload.get("cycle_id") == report.cycle_id
    ]
    assert failed_events
    assert failed_events[-1].payload["failure_kind"] == "convergence_limit"
    assert failed_events[-1].payload["partial_cycles"] == "2"

    evidence_result = coordinator._closed_loop_evidence_boundary.get(
        report.cycle_id
    )
    assert evidence_result is not None
    assert evidence_result.recorded
    assert evidence_result.evidence is not None

    evidence_feedback = evidence_result.evidence.payload["feedback"]
    assert any(
        item["metadata"].get("failure_detail", {}).get("failure_kind")
        == "convergence_limit"
        for item in evidence_feedback
    )

    with pytest.raises(ValueError, match="terminal lifecycle state"):
        coordinator.run(
            _result(
                CognitiveResultStatus.PARTIAL,
                result_id="result:partial-limit-after-terminal",
            ),
            optimize=False,
        )


def test_partial_cycle_limit_must_be_positive_integer() -> None:
    with pytest.raises(ValueError, match="max_partial_cycles must be >= 1"):
        LearningClosedLoopCoordinator(SH3Kernel(), max_partial_cycles=0)

    with pytest.raises(TypeError, match="max_partial_cycles must be an integer"):
        LearningClosedLoopCoordinator(
            SH3Kernel(),
            max_partial_cycles=True,
        )
