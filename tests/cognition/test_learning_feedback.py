from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cognition.feedback import (
    CognitiveFeedback,
    CognitiveFeedbackBridge,
    CognitiveFeedbackKind,
    CognitiveFeedbackStore,
)
from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from infrastructure.event_bus import EventBus, EventBusPublisher
from infrastructure.events import Event
from kernel.core import SH3Kernel

NOW = datetime(2026, 10, 5, 0, 0, tzinfo=UTC)


def _feedback() -> CognitiveFeedback:
    return CognitiveFeedback.create(
        cycle_id="cycle-1",
        goal_id="goal-1",
        kind=CognitiveFeedbackKind.CLOSED_LOOP,
        source_id="source-1",
        success=True,
        score=0.8,
        reason="closed loop completed",
        correlation_id="corr-1",
        causation_id="cause-1",
        trace_id="trace-1",
        tenant_id="tenant-1",
        created_at=NOW,
        metadata={"result_id": "result-1"},
    )


def test_feedback_is_deterministic_and_immutable() -> None:
    first = _feedback()
    second = _feedback()
    assert first == second
    assert first.feedback_id == second.feedback_id
    with pytest.raises(AttributeError):
        first.success = False  # type: ignore[misc]


def test_feedback_validates_score_and_trace_fields() -> None:
    with pytest.raises(ValueError, match=r"between 0\.0 and 1\.0"):
        CognitiveFeedback.create(
            cycle_id="cycle-1",
            goal_id="goal-1",
            kind=CognitiveFeedbackKind.LEARNING,
            source_id="source-1",
            success=True,
            score=1.1,
            reason="invalid",
            correlation_id="corr-1",
        )
    with pytest.raises(ValueError, match="trace_id must not be empty"):
        CognitiveFeedback.create(
            cycle_id="cycle-1",
            goal_id="goal-1",
            kind=CognitiveFeedbackKind.LEARNING,
            source_id="source-1",
            success=True,
            score=0.5,
            reason="invalid",
            correlation_id="corr-1",
            trace_id="",
        )


def test_feedback_store_is_idempotent_and_conflict_safe() -> None:
    store = CognitiveFeedbackStore()
    feedback = _feedback()
    assert store.register(feedback) is feedback
    assert store.register(feedback) is feedback
    assert store.get(feedback.feedback_id) == feedback
    assert store.latest() == feedback
    assert store.for_goal("goal-1") == (feedback,)
    conflicting = CognitiveFeedback(
        feedback.feedback_id,
        feedback.cycle_id,
        feedback.goal_id,
        feedback.kind,
        feedback.source_id,
        False,
        feedback.score,
        feedback.created_at,
        feedback.reason,
        feedback.correlation_id,
        feedback.causation_id,
        feedback.trace_id,
        feedback.tenant_id,
        feedback.metadata,
    )
    with pytest.raises(ValueError, match="conflicting feedback"):
        store.register(conflicting)


def test_feedback_round_trips_from_dict() -> None:
    feedback = _feedback()
    restored = CognitiveFeedback.from_dict(feedback.to_dict())
    assert restored == feedback


def test_feedback_bridge_records_event_feedback() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    kernel = SH3Kernel()
    bridge = CognitiveFeedbackBridge(kernel.cognition, publisher, subscriber_id="test-feedback-bridge")
    feedback = _feedback()
    event = Event.create(
        event_name="CognitiveFeedbackRecorded",
        producer="test",
        payload={"feedback": feedback.to_dict()},
        category=Category.LEARNING,
        event_type=EventType.CREATED,
        correlation_id="corr-1",
    )
    publisher.publish(event)
    assert kernel.cognition.feedback_records() == (feedback,)
    bridge.set_event_publisher(None)


def test_feedback_bridge_ignores_malformed_feedback_event() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    kernel = SH3Kernel()
    CognitiveFeedbackBridge(kernel.cognition, publisher, subscriber_id="test-feedback-malformed")
    event = Event.create(
        event_name="CognitiveFeedbackRecorded",
        producer="test",
        payload={"feedback": {"feedback_id": "broken"}},
        category=Category.LEARNING,
        event_type=EventType.CREATED,
        correlation_id="corr-1",
    )
    publisher.publish(event)
    assert kernel.cognition.feedback_records() == ()


def test_kernel_creates_closed_loop_coordinator() -> None:
    kernel = SH3Kernel()
    assert kernel.learning_feedback_loop.started is False
    assert kernel.learning_feedback_loop.records() == ()


def test_feedback_kind_is_explicit() -> None:
    values = {item.value for item in CognitiveFeedbackKind}
    assert values == {"closed_loop", "learning", "optimization", "self_healing"}
