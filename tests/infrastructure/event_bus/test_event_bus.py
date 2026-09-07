from __future__ import annotations

import pytest

from infrastructure.event_bus.dead_letter import DeadLetterReason
from infrastructure.event_bus.event_bus import EventBus
from infrastructure.event_bus.queue import EventQueue
from infrastructure.event_bus.retry import RetryPolicy
from infrastructure.event_bus.router import EventSubscription
from infrastructure.events.model import Event


def make_event(name: str = "test.event") -> Event:
    return Event.create(event_name=name, producer="test")


def test_publish_and_delivery() -> None:
    received: list[str] = []

    def handler(event: Event) -> None:
        received.append(event.id)

    bus = EventBus()
    bus.subscribe(EventSubscription("subscriber", handler))
    event = make_event()
    result = bus.publish(event)
    assert result.accepted
    assert result.queued
    assert result.delivered
    assert result.delivery is not None
    assert result.delivery.successful == 1
    assert received == [event.id]
    snapshot = bus.snapshot()
    assert snapshot.published == 1
    assert snapshot.accepted == 1
    assert snapshot.rejected == 0
    assert snapshot.delivered == 1
    assert snapshot.failed == 0
    assert snapshot.queue_size == 0


def test_process_uses_queued_events() -> None:
    received: list[str] = []

    def handler(event: Event) -> None:
        received.append(event.id)

    bus = EventBus()
    bus.subscribe(EventSubscription("subscriber", handler))
    event = make_event()
    bus.queue.put(event)
    reports = bus.process(limit=1)
    assert len(reports) == 1
    assert reports[0].successful == 1
    assert received == [event.id]
    assert bus.empty()


def test_process_one_empty_returns_none() -> None:
    assert EventBus().process_one() is None


def test_failure_triggers_retry() -> None:
    attempts: list[str] = []

    def failing(event: Event) -> None:
        attempts.append(event.id)
        raise RuntimeError("boom")

    bus = EventBus(retry_policy=RetryPolicy(max_attempts=3, initial_delay=0.0))
    bus.subscribe(EventSubscription("subscriber", failing))
    result = bus.publish(make_event())
    assert result.accepted and result.queued and not result.delivered
    assert result.retry is not None and result.retry.retry
    assert not result.dead_lettered
    assert attempts
    assert bus.snapshot().failed == 1
    assert bus.snapshot().retried == 1


def test_retry_exhaustion_routes_to_dead_letter() -> None:
    def failing(_: Event) -> None:
        raise RuntimeError("boom")

    bus = EventBus(retry_policy=RetryPolicy(max_attempts=2, initial_delay=0.0))
    bus.subscribe(EventSubscription("subscriber", failing))
    event = make_event()
    first = bus.publish(event)
    second = bus.publish(event)
    assert first.retry is not None and first.retry.retry
    assert second.retry is not None and second.retry.exhausted
    assert second.dead_lettered
    assert second.error == "RuntimeError: boom"
    entries = bus.dead_letters()
    assert len(entries) == 1
    assert entries[0].reason == DeadLetterReason.RETRY_EXHAUSTED
    assert entries[0].subscriber_id == "subscriber"
    snapshot = bus.snapshot()
    assert snapshot.retried == 1
    assert snapshot.dead_lettered == 1
    assert snapshot.dead_letter_size == 1


def test_retry_event_rejects_when_retry_is_unavailable() -> None:
    bus = EventBus(retry_policy=RetryPolicy(max_attempts=1, initial_delay=10.0))
    result = bus.retry_event(make_event())
    assert not result.accepted
    assert not result.queued
    assert not result.delivered
    assert result.error == "retry not available"


def test_record_success_resets_retry_state() -> None:
    bus = EventBus()
    bus.record_failure("key", RuntimeError("failure"))
    assert bus.retry.attempts("key") == 1
    bus.record_success("key")
    assert bus.retry.attempts("key") == 0
    assert bus.retry.failures("key") == 0


def test_queue_rejection_routes_to_dead_letter() -> None:
    queue = EventQueue("bounded", capacity=1)
    bus = EventBus(queue=queue)
    queue.put(make_event("queued"))
    result = bus.publish(make_event("rejected"))
    assert not result.accepted
    assert not result.queued
    assert not result.delivered
    assert result.dead_lettered
    assert result.error is not None
    assert bus.snapshot().rejected == 1
    assert bus.snapshot().dead_lettered == 1
    assert bus.dead_letters()[0].reason == DeadLetterReason.QUEUE_REJECTED


def test_failure_isolation_and_report() -> None:
    successful: list[str] = []

    def failing(_: Event) -> None:
        raise ValueError("failure")

    def succeeding(event: Event) -> None:
        successful.append(event.id)

    bus = EventBus(retry_policy=RetryPolicy(max_attempts=3, initial_delay=0.0))
    bus.subscribe(EventSubscription("a-failing", failing))
    bus.subscribe(EventSubscription("b-success", succeeding))
    event = make_event()
    result = bus.publish(event)
    assert result.delivery is not None
    assert result.delivery.total == 2
    assert result.delivery.successful == 1
    assert result.delivery.failed == 1
    assert not result.delivered
    assert successful == [event.id]


def test_dead_letter_release_and_clear() -> None:
    def failing(_: Event) -> None:
        raise RuntimeError("boom")

    bus = EventBus(retry_policy=RetryPolicy(max_attempts=1))
    bus.subscribe(EventSubscription("subscriber", failing))
    result = bus.publish(make_event())
    assert result.dead_lettered
    assert bus.dead_letter_size() == 1
    entry = bus.release_dead_letter()
    assert entry.reason == DeadLetterReason.RETRY_EXHAUSTED
    assert bus.dead_letter_size() == 0
    bus.publish(make_event())
    cleared = bus.clear_dead_letters()
    assert len(cleared) == 1
    assert bus.dead_letter_size() == 0


def test_metrics_and_reset() -> None:
    bus = EventBus()
    bus.publish(make_event())
    snapshot = bus.snapshot()
    assert snapshot.published == 1
    assert snapshot.accepted == 1
    bus.reset_metrics()
    reset = bus.snapshot()
    assert reset.published == 0
    assert reset.accepted == 0
    assert reset.rejected == 0
    assert reset.delivered == 0
    assert reset.failed == 0
    assert reset.retried == 0
    assert reset.dead_lettered == 0
    assert reset.queue_size == 0


def test_close_is_idempotent_and_blocks_operations() -> None:
    bus = EventBus()
    bus.close()
    bus.close()
    assert bus.closed
    with pytest.raises(RuntimeError, match="event bus is closed"):
        bus.publish(make_event())
    with pytest.raises(RuntimeError, match="event bus is closed"):
        bus.process()
    with pytest.raises(RuntimeError, match="event bus is closed"):
        bus.subscribe(EventSubscription("subscriber", lambda _: None))


def test_publish_many_requires_tuple_and_returns_results() -> None:
    bus = EventBus()
    results = bus.publish_many((make_event("a"), make_event("b")))
    assert len(results) == 2
    assert all(result.accepted for result in results)
    assert bus.snapshot().published == 2
