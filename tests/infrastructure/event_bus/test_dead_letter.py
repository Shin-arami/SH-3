from __future__ import annotations

import pytest

from infrastructure.event_bus.dead_letter import DeadLetterQueue, DeadLetterReason
from infrastructure.events.model import Event


def make_event(name: str = "test.event") -> Event:
    return Event.create(event_name=name, producer="test")


def test_store() -> None:
    queue = DeadLetterQueue()
    event = make_event()
    entry = queue.put(
        event, reason=DeadLetterReason.DELIVERY_FAILED, error="boom", subscriber_id="subscriber"
    )
    assert entry.event is event
    assert entry.sequence == 0
    assert entry.reason == DeadLetterReason.DELIVERY_FAILED
    assert entry.error == "boom"
    assert entry.subscriber_id == "subscriber"
    assert queue.size() == 1
    assert queue.stored() == 1


def test_capacity() -> None:
    queue = DeadLetterQueue(capacity=1)
    queue.put(make_event())
    with pytest.raises(OverflowError, match="dead-letter queue is full"):
        queue.put(make_event())
    snapshot = queue.snapshot()
    assert snapshot.size == 1
    assert snapshot.rejected == 1
    assert snapshot.full


def test_retrieval_and_fifo() -> None:
    queue = DeadLetterQueue()
    first = queue.put(make_event("first"))
    second = queue.put(make_event("second"))
    assert queue.peek() == first
    assert queue.get() == first
    assert queue.get_nowait() == second
    assert queue.empty()
    assert queue.released() == 2


def test_filtering() -> None:
    queue = DeadLetterQueue()
    first = make_event("first")
    second = make_event("second")
    queue.put(first, reason=DeadLetterReason.DELIVERY_FAILED)
    queue.put(second, reason=DeadLetterReason.RETRY_EXHAUSTED)
    queue.put(first, reason=DeadLetterReason.RETRY_EXHAUSTED)
    by_event = queue.find_by_event(first.id)
    by_reason = queue.find_by_reason(DeadLetterReason.RETRY_EXHAUSTED)
    assert len(by_event) == 2
    assert len(by_reason) == 2
    assert all(entry.event.id == first.id for entry in by_event)
    assert all(entry.reason == DeadLetterReason.RETRY_EXHAUSTED for entry in by_reason)


def test_statistics() -> None:
    queue = DeadLetterQueue()
    queue.put(make_event())
    queue.put(make_event())
    queue.get()
    snapshot = queue.snapshot()
    assert snapshot.stored == 2
    assert snapshot.released == 1
    assert snapshot.rejected == 0
    assert snapshot.size == 1
    assert snapshot.sequence == 2
