from __future__ import annotations

from foundation.Enums.event import EventType
from infrastructure.event_bus import EventBus, EventBusPublisher
from infrastructure.events import Event
from kernel.core import SH3Kernel


def _build_bus() -> tuple[EventBus, EventBusPublisher]:
    bus = EventBus()
    return bus, EventBusPublisher(bus)


def _publish_learning_feedback(
    bus: EventBus,
    *,
    strategy: str,
    success: bool,
    correlation_id: str,
    trace_id: str,
) -> None:
    bus.publish(
        Event.create(
            event_name="HealingFeedbackRecorded",
            producer="p1-4-test",
            payload={
                "recovery_id": f"p1-4-{strategy}",
                "success": success,
                "strategy": strategy,
                "feedback": {
                    "attempt": 1,
                    "score": 1.0 if success else 0.0,
                    "error_type": "RuntimeError",
                    "recovery_error": None if success else "recovery failure",
                    "details": {"strategy": strategy, "source": "p1-4"},
                },
            },
            event_type=EventType.CREATED,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )
    )


def test_p1_4_event_driven_learning_changes_strategy_selection() -> None:
    bus, publisher = _build_bus()
    kernel = SH3Kernel(event_publisher=publisher)
    healer = kernel.meta_controller.healer
    for _ in range(3):
        _publish_learning_feedback(
            bus,
            strategy="retry_safe",
            success=True,
            correlation_id="p1-4-selection",
            trace_id="p1-4-selection-trace",
        )
        _publish_learning_feedback(
            bus,
            strategy="rebuild_context",
            success=False,
            correlation_id="p1-4-selection",
            trace_id="p1-4-selection-trace",
        )

    records = kernel.learning_loop.records()
    assert len(records) == 6
    assert all(record["domain"] == "self_healing.recovery" for record in records)
    assert sum(record["success"] for record in records) == 3
    assert sum(record["score"] for record in records) == 3.0
    assert (
        healer._select_strategy(healer.detect(ValueError("p1-4"), {}))
        == "retry_safe"
    )


def test_p1_4_event_driven_failure_has_zero_score() -> None:
    bus, publisher = _build_bus()
    kernel = SH3Kernel(event_publisher=publisher)
    _publish_learning_feedback(
        bus,
        strategy="fallback_default",
        success=False,
        correlation_id="p1-4-failure",
        trace_id="p1-4-failure-trace",
    )

    record = kernel.learning_loop.records()[-1]
    assert record["success"] is False
    assert record["score"] == 0.0
    assert record["details"]["strategy"] == "fallback_default"


def test_p1_4_event_driven_learning_summary_uses_dict_records() -> None:
    bus, publisher = _build_bus()
    kernel = SH3Kernel(event_publisher=publisher)
    for _ in range(3):
        _publish_learning_feedback(
            bus,
            strategy="retry_safe",
            success=True,
            correlation_id="p1-4-summary",
            trace_id="p1-4-summary-trace",
        )

    summary = kernel.meta_controller.healer.learning_summary()
    assert summary["record_count"] == 3
    assert summary["successes"] == 3
    assert summary["failures"] == 0
    assert summary["success_rate"] == 1.0
    assert summary["strategies"]["retry_safe"]["success_rate"] == 1.0
