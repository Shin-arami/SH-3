from __future__ import annotations

from infrastructure.event_bus import (
    EventBus,
    EventBusPublisher,
    EventPublisher,
    EventSink,
    PublishResult,
)
from infrastructure.events.model import Event


def _event(name: str = "ComponentStarted") -> Event:
    return Event.create(
        event_name=name,
        producer="test",
        payload={"component": "test"},
    )


def test_publisher_is_event_publisher() -> None:
    publisher = EventBusPublisher(EventBus())
    assert isinstance(publisher, EventPublisher)


def test_publisher_delegates_to_event_bus() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    event = _event()

    result = publisher.publish(event)

    assert result.event_id == event.id
    assert result.accepted is True
    assert result.queued is True


def test_publisher_exposes_event_bus() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)

    assert publisher.event_bus is bus


def test_publisher_rejects_invalid_event_bus() -> None:
    try:
        EventBusPublisher(object())  # type: ignore[arg-type]
    except TypeError as exc:
        assert str(exc) == "event_bus must be EventBus"
    else:
        raise AssertionError("TypeError was not raised")


def test_publisher_preserves_publish_result() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    event = _event()

    result = publisher.publish(event)

    assert isinstance(result, PublishResult)
    assert result.event_id == event.id


def test_as_sink_returns_callable() -> None:
    publisher = EventBusPublisher(EventBus())

    sink = publisher.as_sink()

    assert callable(sink)
    assert sink(_event()).accepted is True


def test_event_sink_accepts_publish_method() -> None:
    publisher = EventBusPublisher(EventBus())
    sink: EventSink = publisher.publish

    result = sink(_event())

    assert result.accepted is True


def test_fake_publisher_is_replaceable() -> None:
    bus = EventBus()
    expected = bus.publish(_event())
    results: list[str] = []

    class FakePublisher:
        def publish(self, event: Event) -> PublishResult:
            results.append(event.id)
            return expected

    publisher: EventPublisher = FakePublisher()
    event = _event()

    result = publisher.publish(event)

    assert results == [event.id]
    assert result is expected


def test_publisher_does_not_change_event() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    event = _event()
    before = event.metadata

    publisher.publish(event)

    assert event.metadata is before
