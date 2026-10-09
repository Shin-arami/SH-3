from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime

from cognition.contracts import CognitiveGoal, CognitiveResult, CognitiveResultStatus
from infrastructure.event_bus import EventBus, EventBusPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from kernel.core import SH3Kernel
from kernel.learning_feedback_loop import ClosedLoopStatus

NOW = datetime(2026, 10, 5, 0, 0, tzinfo=UTC)


def _result(status: CognitiveResultStatus = CognitiveResultStatus.SUCCESS) -> CognitiveResult:
    goal = CognitiveGoal.create("prepare release", created_at=NOW, correlation_id="corr-phase3", trace_id="trace-phase3")
    return CognitiveResult.create(
        goal,
        status=status,
        lifecycle_state=goal.lifecycle_state,
        created_at=NOW,
        error_type="RuntimeError" if status is CognitiveResultStatus.FAILURE else None,
        error_message="phase3 failure" if status is CognitiveResultStatus.FAILURE else None,
        output={
            "goal": goal.to_dict(),
            "plan": {"plan_id": "plan:phase3", "steps": ["prepare release"]},
            "decision": {"decision_id": "decision:phase3", "selected_option": "prepare release"},
        },
        result_id="result:phase3" if status is CognitiveResultStatus.SUCCESS else "result:phase3-failure",
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
