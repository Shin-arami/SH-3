from __future__ import annotations

from typing import Any

import pytest

from infrastructure.event_bus import PublishResult
from infrastructure.events.model import Event
from self_healing.core import SelfHealingCore, SelfHealingException


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def publish(self, event: Event) -> PublishResult:
        self.events.append(event)
        return PublishResult(
            event_id=event.id,
            accepted=True,
            queued=False,
            delivered=False,
            retry=None,
            dead_lettered=False,
            error=None,
        )


def test_detect_publishes_failure_detected_event() -> None:
    publisher = RecordingPublisher()
    healer = SelfHealingCore(event_publisher=publisher)

    snapshot = healer.detect(
        KeyError("missing"),
        {"operation": "test"},
    )

    assert [event.name for event in publisher.events] == [
        "FailureDetected",
    ]
    event = publisher.events[0]
    assert event.metadata.producer == "healing"
    assert event.payload["failure_id"] == snapshot.trace_id
    assert event.payload["error"] == str(snapshot.error)
    assert event.trace_id == snapshot.trace_id
    assert event.correlation_id == snapshot.trace_id


def test_recovery_publishes_lifecycle_events() -> None:
    publisher = RecordingPublisher()
    healer = SelfHealingCore(event_publisher=publisher)

    snapshot = healer.detect(KeyError("missing"))
    result = healer.recover(snapshot)

    assert result["status"] == "fallback_used"
    assert [event.name for event in publisher.events] == [
        "FailureDetected",
        "RecoveryPlanned",
        "RecoveryStarted",
        "HealingFeedbackRecorded",
        "RecoveryCompleted",
    ]


def test_failed_recovery_publishes_failure_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publisher = RecordingPublisher()
    healer = SelfHealingCore(event_publisher=publisher)

    def failing_recovery(
        self: SelfHealingCore,
        snapshot: Any,
    ) -> Any:
        raise RuntimeError("recovery failure")

    monkeypatch.setattr(
        SelfHealingCore,
        "_fallback",
        failing_recovery,
    )

    snapshot = healer.detect(KeyError("missing"))

    with pytest.raises(SelfHealingException):
        healer.recover(snapshot)

    assert [event.name for event in publisher.events] == [
        "FailureDetected",
        "RecoveryPlanned",
        "RecoveryStarted",
        "HealingFeedbackRecorded",
        "RecoveryFailed",
    ]
    assert publisher.events[-1].payload["error"] == "recovery failure"


def test_recover_with_learning_publishes_attempt_events() -> None:
    publisher = RecordingPublisher()
    healer = SelfHealingCore(event_publisher=publisher)

    snapshot = healer.detect(KeyError("missing"))
    result = healer.recover_with_learning(snapshot, max_attempts=2)

    assert result["status"] == "fallback_used"
    names = [event.name for event in publisher.events]
    assert names == [
        "FailureDetected",
        "RecoveryPlanned",
        "RecoveryStarted",
        "HealingFeedbackRecorded",
        "RecoveryCompleted",
    ]


def test_publisher_failure_does_not_break_recovery() -> None:
    class FailingPublisher:
        def publish(self, event: Event) -> PublishResult:
            raise RuntimeError("publisher failure")

    healer = SelfHealingCore(
        event_publisher=FailingPublisher(),
    )

    snapshot = healer.detect(KeyError("missing"))
    result = healer.recover(snapshot)

    assert result["status"] == "fallback_used"
    assert healer.detected == 1
    assert healer.recovered == 1


def test_existing_self_healing_api_without_publisher() -> None:
    healer = SelfHealingCore()

    snapshot = healer.detect(KeyError("missing"))
    result = healer.recover(snapshot)

    assert result["status"] == "fallback_used"
