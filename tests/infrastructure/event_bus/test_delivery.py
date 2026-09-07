from __future__ import annotations

from infrastructure.event_bus.delivery import DeliveryStatus, EventDelivery
from infrastructure.event_bus.router import EventRouter, EventSubscription
from infrastructure.events.model import Event


def make_event() -> Event:
    return Event.create(event_name="test.event", producer="test")


def test_success_delivery() -> None:
    received: list[str] = []

    def handler(event: Event) -> None:
        received.append(event.id)

    router = EventRouter()
    router.subscribe(EventSubscription("subscriber", handler))
    event = make_event()
    report = EventDelivery(router).deliver(event)
    assert received == [event.id]
    assert report.total == 1
    assert report.successful == 1
    assert report.failed == 0
    assert report.completed
    assert report.succeeded
    assert report.results[0].status == DeliveryStatus.SUCCESS
    assert report.results[0].error is None


def test_failure_isolated_between_targets() -> None:
    received: list[str] = []

    def failing(_: Event) -> None:
        raise RuntimeError("boom")

    def succeeding(event: Event) -> None:
        received.append(event.id)

    router = EventRouter()
    router.subscribe(EventSubscription("a-failing", failing))
    router.subscribe(EventSubscription("b-success", succeeding))
    report = EventDelivery(router).deliver(make_event())
    assert report.total == 2
    assert report.successful == 1
    assert report.failed == 1
    assert report.completed
    assert received
    failed = next(result for result in report.results if result.failed)
    assert failed.error == "RuntimeError: boom"


def test_delivery_report_empty() -> None:
    event = make_event()
    report = EventDelivery(EventRouter()).deliver(event)
    assert report.event_id == event.id
    assert report.total == 0
    assert report.successful == 0
    assert report.failed == 0
    assert report.skipped == 0
    assert report.empty
    assert report.completed
    assert not report.succeeded
