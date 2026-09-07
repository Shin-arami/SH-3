from __future__ import annotations

from threading import Thread

import pytest

from infrastructure.event_bus.queue import EventQueue, EventQueueSet
from infrastructure.events.model import Event


def make_event(name: str = "test.event") -> Event:
    return Event.create(event_name=name, producer="test")


def test_fifo() -> None:
    queue = EventQueue("fifo")
    first = queue.put(make_event("first"))
    second = queue.put(make_event("second"))
    assert queue.get() == first
    assert queue.get() == second
    assert first.sequence == 0
    assert second.sequence == 1


def test_bounded_capacity_and_statistics() -> None:
    queue = EventQueue("bounded", capacity=1)
    queue.put(make_event())
    with pytest.raises(OverflowError, match="queue is full"):
        queue.put(make_event())
    snapshot = queue.snapshot()
    assert snapshot.size == 1
    assert snapshot.capacity == 1
    assert snapshot.published == 1
    assert snapshot.consumed == 0
    assert snapshot.rejected == 1
    assert snapshot.sequence == 1
    assert snapshot.full


def test_put_many_is_atomic_on_capacity_rejection() -> None:
    queue = EventQueue("bounded", capacity=2)
    with pytest.raises(OverflowError):
        queue.put_many((make_event("a"), make_event("b"), make_event("c")))
    assert queue.empty()
    assert queue.snapshot().published == 0
    assert queue.snapshot().rejected == 3


def test_wait_get_returns_item_after_notification() -> None:
    queue = EventQueue("wait")
    result: list[object] = []

    def consumer() -> None:
        result.append(queue.wait_get(timeout=1.0))

    thread = Thread(target=consumer)
    thread.start()
    queue.put(make_event())
    thread.join(timeout=2.0)
    assert not thread.is_alive()
    assert len(result) == 1
    assert result[0] is not None


def test_wait_get_timeout_returns_none() -> None:
    assert EventQueue("wait").wait_get(timeout=0.01) is None


def test_close_wakes_waiter_and_rejects_put() -> None:
    queue = EventQueue("close")
    result: list[object] = []

    def consumer() -> None:
        result.append(queue.wait_get(timeout=1.0))

    thread = Thread(target=consumer)
    thread.start()
    queue.close()
    thread.join(timeout=2.0)
    assert not thread.is_alive()
    assert result == [None]
    assert queue.closed
    with pytest.raises(RuntimeError, match="queue is closed"):
        queue.put(make_event())


def test_statistics_after_consumption_and_drain() -> None:
    queue = EventQueue("stats")
    queue.put_many((make_event("a"), make_event("b"), make_event("c")))
    queue.get()
    queue.drain()
    snapshot = queue.snapshot()
    assert snapshot.published == 3
    assert snapshot.consumed == 3
    assert snapshot.size == 0
    assert snapshot.sequence == 3


def test_queue_set() -> None:
    queues = EventQueueSet()
    queue = queues.create("main", capacity=2)
    assert queues.get("main") is queue
    assert queues.contains("main")
    assert queues.names() == ("main",)
    assert queues.count() == 1
    assert queues.remove("main") is queue
    assert not queues.contains("main")
