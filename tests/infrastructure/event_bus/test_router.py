from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from foundation.Enums.event import EventType
from foundation.Enums.priority import Priority
from infrastructure.event_bus.router import EventRouter, EventSubscription
from infrastructure.events.model import Event


def make_event(
    *,
    name: str = "test.event",
    priority: Priority = Priority.NORMAL,
    producer: str = "test",
    tags: dict[str, Any] | None = None,
    event_type: EventType = EventType.UNKNOWN,
) -> Event:
    return Event.create(
        event_name=name,
        producer=producer,
        priority=priority,
        tags=tags or {},
        event_type=event_type,
    )


def handler(_: Event) -> None:
    pass


def test_subscribe_and_unsubscribe() -> None:
    router = EventRouter()
    subscription = EventSubscription("subscriber", handler)
    router.subscribe(subscription)
    assert router.contains("subscriber")
    assert router.count() == 1
    assert router.subscribers() == (subscription,)
    assert router.unsubscribe("subscriber") == subscription
    assert not router.contains("subscriber")
    assert router.count() == 0


def test_duplicate_subscribe_requires_replace() -> None:
    router = EventRouter()
    first = EventSubscription("subscriber", handler)
    second = EventSubscription(
        "subscriber",
        handler,
        event_name="other",
    )
    router.subscribe(first)
    with pytest.raises(ValueError, match="already registered"):
        router.subscribe(second)
    router.subscribe(second, replace=True)
    assert router.subscribers() == (second,)


def test_filtering() -> None:
    router = EventRouter()
    router.subscribe(
        EventSubscription("name", handler, event_name="wanted")
    )
    router.subscribe(
        EventSubscription(
            "type",
            handler,
            event_type=EventType.UNKNOWN,
        )
    )
    router.subscribe(
        EventSubscription(
            "version",
            handler,
            event_version="2.0.0",
        )
    )
    router.subscribe(
        EventSubscription(
            "producer",
            handler,
            producer="producer-a",
        )
    )
    router.subscribe(
        EventSubscription(
            "tags",
            handler,
            tags=(("env", "prod"),),
        )
    )
    event = make_event(
        name="wanted",
        producer="producer-a",
        tags={"env": "prod"},
    )
    ids = {target.subscriber_id for target in router.route(event)}
    assert ids == {"name", "type", "producer", "tags"}


def test_min_priority_filter() -> None:
    router = EventRouter()
    router.subscribe(
        EventSubscription(
            "high-only",
            handler,
            min_priority=Priority.HIGH,
        )
    )
    assert router.route(make_event(priority=Priority.LOW)) == ()
    assert [
        target.subscriber_id
        for target in router.route(make_event(priority=Priority.HIGH))
    ] == ["high-only"]


def test_priority_ordering_is_deterministic() -> None:
    router = EventRouter()
    router.subscribe(EventSubscription("b", handler, priority=10))
    router.subscribe(EventSubscription("a", handler, priority=10))
    router.subscribe(EventSubscription("c", handler, priority=20))
    assert [
        target.subscriber_id
        for target in router.route(make_event())
    ] == ["c", "a", "b"]


def test_enable_disable() -> None:
    router = EventRouter()
    router.subscribe(EventSubscription("subscriber", handler))
    router.disable("subscriber")
    assert router.route(make_event()) == ()
    router.enable("subscriber")
    assert len(router.route(make_event())) == 1


def test_thread_safe_subscribe_and_unsubscribe() -> None:
    router = EventRouter()

    def worker(index: int) -> None:
        subscriber_id = f"s-{index}"
        router.subscribe(
            EventSubscription(subscriber_id, handler)
        )
        assert router.contains(subscriber_id)
        router.unsubscribe(subscriber_id)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(worker, range(100)))

    assert router.count() == 0
