from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier, Lock
from time import sleep

import pytest

from cognition.feedback import CognitiveFeedback, CognitiveFeedbackKind
from cognition.feedback_boundary import (
    CognitiveFeedbackBoundary,
    CognitiveFeedbackRequest,
    CognitiveFeedbackResult,
)
from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from infrastructure.event_bus import EventBus, EventBusPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from kernel import SH3Kernel

NOW = datetime(2026, 10, 5, 0, 0, tzinfo=UTC)


def _feedback() -> CognitiveFeedback:
    return CognitiveFeedback.create(
        cycle_id="cycle-11-4",
        goal_id="goal-11-4",
        kind=CognitiveFeedbackKind.CLOSED_LOOP,
        source_id="cycle-11-4",
        success=True,
        score=0.9,
        reason="closed loop completed",
        correlation_id="corr-11-4",
        trace_id="trace-11-4",
        tenant_id="tenant-11-4",
        created_at=NOW,
    )


def _context() -> EventPropagationContext:
    return EventPropagationContext.create(
        correlation_id="corr-11-4",
        trace_id="trace-11-4",
        tenant_id="tenant-11-4",
        causation_id="cause-11-4",
    )


def test_feedback_request_is_deterministic_and_immutable() -> None:
    feedback = _feedback()
    first = CognitiveFeedbackRequest.from_feedback(feedback, context=_context(), created_at=NOW)
    second = CognitiveFeedbackRequest.from_feedback(feedback, context=_context(), created_at=NOW)
    assert first == second
    assert first.request_id == second.request_id
    with pytest.raises(AttributeError):
        first.request_id = "changed"  # type: ignore[misc]


def test_feedback_request_identity_is_context_scoped() -> None:
    feedback = _feedback()
    first_context = _context()
    second_context = EventPropagationContext.create(
        correlation_id="corr-11-4-other",
        causation_id="cause-11-4-other",
        trace_id="trace-11-4-other",
        tenant_id="tenant-11-4-other",
    )

    first = CognitiveFeedbackRequest.from_feedback(
        feedback, context=first_context, created_at=NOW
    )
    replay = CognitiveFeedbackRequest.from_feedback(
        feedback, context=first_context, created_at=NOW
    )
    other_trace = CognitiveFeedbackRequest.from_feedback(
        feedback, context=second_context, created_at=NOW
    )

    assert first.request_id == replay.request_id
    assert first.request_id != other_trace.request_id


def test_feedback_boundary_serializes_concurrent_duplicate_requests() -> None:
    class CountingCognition:
        def __init__(self) -> None:
            self.calls = 0
            self.lock = Lock()

        def record_feedback(self, feedback: CognitiveFeedback) -> CognitiveFeedback:
            with self.lock:
                self.calls += 1
            sleep(0.04)
            return feedback

    cognition = CountingCognition()
    boundary = CognitiveFeedbackBoundary(cognition)
    feedback = _feedback()
    context = _context()
    start = Barrier(8)

    def record_duplicate(_: int) -> CognitiveFeedbackResult:
        start.wait(timeout=5)
        return boundary.record(
            feedback,
            context=context,
            created_at=NOW
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = tuple(executor.map(record_duplicate, range(8)))

    assert cognition.calls == 1
    assert all(result is results[0] for result in results)
    assert boundary.records() == (results[0],)


def test_failed_feedback_record_can_be_retried_with_same_request_identity() -> None:
    class FlakyCognition:
        def __init__(self) -> None:
            self.calls = 0

        def record_feedback(self, feedback: CognitiveFeedback) -> CognitiveFeedback:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("temporary feedback storage failure")
            return feedback

    cognition = FlakyCognition()
    boundary = CognitiveFeedbackBoundary(cognition)
    feedback = _feedback()
    context = _context()

    first = boundary.record(feedback, context=context, created_at=NOW)
    second = boundary.record(feedback, context=context, created_at=NOW)

    assert first.success is False
    assert second.success is True
    assert second.request_id == first.request_id
    assert cognition.calls == 2
    assert boundary.records() == (second,)


def test_feedback_request_event_replay_does_not_repeat_storage() -> None:
    class CountingCognition:
        def __init__(self) -> None:
            self.calls = 0

        def record_feedback(self, feedback: CognitiveFeedback) -> CognitiveFeedback:
            self.calls += 1
            return feedback

    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    bus.subscribe(
        EventSubscription(
            subscriber_id="11-4-replay-audit",
            handler=events.append,
            priority=-100,
        )
    )
    cognition = CountingCognition()
    boundary = CognitiveFeedbackBoundary(cognition, publisher)

    result = boundary.record(_feedback(), context=_context(), created_at=NOW)
    requested = next(event for event in events if event.name == "CognitiveFeedbackRequested")
    publisher.publish(requested)

    assert result.success is True
    assert cognition.calls == 1
    assert len([event for event in events if event.name == "CognitiveFeedbackRecorded"]) == 1


def test_feedback_boundary_records_without_event_bus() -> None:
    kernel = SH3Kernel()
    boundary = CognitiveFeedbackBoundary(kernel.cognition)
    result = boundary.record(_feedback(), context=_context(), created_at=NOW)
    assert result.success is True
    assert result.feedback_id == _feedback().feedback_id
    assert kernel.cognition.latest_feedback() is not None
    assert boundary.get(result.request_id) == result


def test_feedback_boundary_uses_event_bus_and_preserves_trace() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    bus.subscribe(EventSubscription(subscriber_id="11-4-audit", handler=events.append, priority=-100), replace=True)
    kernel = SH3Kernel()
    boundary = CognitiveFeedbackBoundary(kernel.cognition, publisher)
    result = boundary.record(_feedback(), context=_context(), created_at=NOW)
    assert result.success is True
    names = [event.name for event in events]
    assert names == ["CognitiveFeedbackRequested", "CognitiveFeedbackRecorded"]
    requested, recorded = events
    assert requested.metadata.correlation_id == "corr-11-4"
    assert requested.metadata.causation_id == "cause-11-4"
    assert recorded.metadata.causation_id == requested.metadata.event_id
    assert recorded.metadata.trace_id == "trace-11-4"
    assert recorded.metadata.tenant_id == "tenant-11-4"
    assert recorded.payload["feedback"]["feedback_id"] == result.feedback_id


def test_feedback_boundary_is_idempotent() -> None:
    kernel = SH3Kernel()
    boundary = CognitiveFeedbackBoundary(kernel.cognition)
    feedback = _feedback()
    first = boundary.record(feedback, context=_context(), created_at=NOW)
    second = boundary.record(feedback, context=_context(), created_at=NOW)
    assert first is second
    assert boundary.records() == (first,)
    assert kernel.cognition.feedback_records() == (feedback,)


def test_feedback_boundary_rebinds_event_bus_subscription() -> None:
    first_bus = EventBus()
    second_bus = EventBus()
    first_publisher = EventBusPublisher(first_bus)
    second_publisher = EventBusPublisher(second_bus)
    kernel = SH3Kernel()
    boundary = CognitiveFeedbackBoundary(kernel.cognition, first_publisher)
    assert first_bus.router.contains("cognition.feedback-boundary")
    boundary.set_event_publisher(second_publisher)
    assert not first_bus.router.contains("cognition.feedback-boundary")
    assert second_bus.router.contains("cognition.feedback-boundary")


def test_feedback_boundary_rejects_storage_conflict() -> None:
    class ConflictingCognition:
        def record_feedback(self, feedback: CognitiveFeedback) -> CognitiveFeedback:
            return CognitiveFeedback.create(
                cycle_id=feedback.cycle_id,
                goal_id=feedback.goal_id,
                kind=feedback.kind,
                source_id=feedback.source_id,
                success=False,
                score=feedback.score,
                reason=feedback.reason,
                correlation_id=feedback.correlation_id,
                trace_id=feedback.trace_id,
                created_at=feedback.created_at,
                feedback_id=feedback.feedback_id,
            )

    boundary = CognitiveFeedbackBoundary(ConflictingCognition())
    result = boundary.record(_feedback(), context=_context(), created_at=NOW)
    assert result.success is False
    assert result.error is not None
    assert "conflict" in result.error.lower()


def test_feedback_boundary_ignores_malformed_requests() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    kernel = SH3Kernel()
    boundary = CognitiveFeedbackBoundary(kernel.cognition, publisher)
    event = Event.create(
        event_name="CognitiveFeedbackRequested",
        producer="test",
        payload={"request": {"request_id": "broken"}},
        category=Category.LEARNING,
        event_type=EventType.START,
        correlation_id="corr-11-4",
    )
    publisher.publish(event)
    assert boundary.records() == ()
    assert kernel.cognition.feedback_records() == ()


def test_kernel_exposes_feedback_boundary_and_coordinator_uses_it() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    kernel = SH3Kernel(event_publisher=publisher)
    assert kernel.feedback_boundary.started is True
    assert kernel.feedback_boundary is kernel.learning_feedback_loop._feedback_boundary

    events: list[Event] = []
    bus.subscribe(EventSubscription(subscriber_id="11-4-order", handler=events.append, priority=-200), replace=True)
    publisher.publish(
        Event.create(
            event_name="CognitiveFeedbackRequested",
            producer="test",
            payload={"request": {}},
            category=Category.LEARNING,
            event_type=EventType.START,
            correlation_id="invalid",
        )
    )
    assert kernel.feedback_boundary.records() == ()
