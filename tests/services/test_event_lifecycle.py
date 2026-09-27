from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrastructure.event_bus import EventBusPublisher, PublishResult
from infrastructure.events.model import Event
from services.base import Service, ServiceException
from services.manager import ServiceManager


@dataclass
class RecordedEvent:
    event: Event


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def publish(self, event: Event) -> PublishResult:
        self.events.append(event)
        return PublishResult(
            event_id=event.id,
            accepted=True,
            queued=True,
            delivered=False,
        )


class DummyService(Service):
    def __init__(
        self,
        name: str = "test",
        *,
        fail_operation: str | None = None,
    ) -> None:
        super().__init__(name)
        self.fail_operation = fail_operation

    def _on_start(self) -> None:
        if self.fail_operation == "start":
            raise RuntimeError("start failure")

    def _on_suspend(self) -> None:
        if self.fail_operation == "suspend":
            raise RuntimeError("suspend failure")

    def _on_resume(self) -> None:
        if self.fail_operation == "resume":
            raise RuntimeError("resume failure")

    def _on_terminate(self) -> None:
        if self.fail_operation == "terminate":
            raise RuntimeError("terminate failure")


def test_start_publishes_service_started() -> None:
    publisher = RecordingPublisher()
    service = DummyService()
    service.set_event_publisher(publisher)

    service.start()

    assert len(publisher.events) == 1
    event = publisher.events[0]
    assert event.metadata.event_name == "ServiceStarted"
    assert event.metadata.producer == "test"
    assert event.payload["service"] == "test"
    assert event.payload["state"] == "ACTIVE"


def test_suspend_publishes_service_suspended() -> None:
    publisher = RecordingPublisher()
    service = DummyService()
    service.set_event_publisher(publisher)
    service.start()
    publisher.events.clear()

    service.suspend()

    assert [event.metadata.event_name for event in publisher.events] == [
        "ServiceSuspended"
    ]
    assert publisher.events[0].payload["state"] == "SUSPENDED"


def test_resume_publishes_service_resumed() -> None:
    publisher = RecordingPublisher()
    service = DummyService()
    service.set_event_publisher(publisher)
    service.start()
    service.suspend()
    publisher.events.clear()

    service.resume()

    assert [event.metadata.event_name for event in publisher.events] == [
        "ServiceResumed"
    ]
    assert publisher.events[0].payload["state"] == "ACTIVE"


def test_terminate_publishes_service_stopped() -> None:
    publisher = RecordingPublisher()
    service = DummyService()
    service.set_event_publisher(publisher)

    service.terminate()

    assert [event.metadata.event_name for event in publisher.events] == [
        "ServiceStopped"
    ]
    assert publisher.events[0].payload["state"] == "TERMINATED"


def test_failed_start_publishes_service_failed() -> None:
    publisher = RecordingPublisher()
    service = DummyService(fail_operation="start")
    service.set_event_publisher(publisher)

    with pytest.raises(ServiceException):
        service.start()

    assert len(publisher.events) == 1
    event = publisher.events[0]
    assert event.metadata.event_name == "ServiceFailed"
    assert event.payload["operation"] == "start"
    assert event.payload["error"] == "start failure"


def test_failed_suspend_publishes_service_failed() -> None:
    publisher = RecordingPublisher()
    service = DummyService(fail_operation="suspend")
    service.set_event_publisher(publisher)
    service.start()
    publisher.events.clear()

    with pytest.raises(ServiceException):
        service.suspend()

    assert [event.metadata.event_name for event in publisher.events] == [
        "ServiceFailed"
    ]
    assert service.active


def test_failed_resume_publishes_service_failed() -> None:
    publisher = RecordingPublisher()
    service = DummyService(fail_operation="resume")
    service.set_event_publisher(publisher)
    service.start()
    service.suspend()
    publisher.events.clear()

    with pytest.raises(ServiceException):
        service.resume()

    assert [event.metadata.event_name for event in publisher.events] == [
        "ServiceFailed"
    ]
    assert service.suspended


def test_failed_terminate_publishes_service_failed() -> None:
    publisher = RecordingPublisher()
    service = DummyService(fail_operation="terminate")
    service.set_event_publisher(publisher)
    service.start()
    publisher.events.clear()

    with pytest.raises(ServiceException):
        service.terminate()

    assert [event.metadata.event_name for event in publisher.events] == [
        "ServiceFailed"
    ]
    assert service.active


def test_publisher_failure_does_not_change_service_state() -> None:
    class FailingPublisher:
        def publish(self, event: Event) -> PublishResult:
            raise RuntimeError("publisher failure")

    service = DummyService()
    service.set_event_publisher(FailingPublisher())

    service.start()

    assert service.active


def test_manager_injects_publisher() -> None:
    publisher = RecordingPublisher()
    manager = ServiceManager(event_publisher=publisher)
    service = DummyService("planner")

    manager.register(service)
    manager.start("planner")

    assert service.event_publisher is publisher
    assert [event.metadata.event_name for event in publisher.events] == [
        "ServiceStarted"
    ]


def test_manager_publisher_can_be_updated() -> None:
    publisher = RecordingPublisher()
    manager = ServiceManager()
    service = DummyService("planner")

    manager.register(service)
    manager.set_event_publisher(publisher)
    manager.start("planner")

    assert [event.metadata.event_name for event in publisher.events] == [
        "ServiceStarted"
    ]


def test_existing_service_api_remains_usable() -> None:
    service = DummyService("planner")

    service.start()
    service.suspend()
    service.resume()
    service.terminate()

    assert service.terminated


def test_real_event_bus_publisher() -> None:
    from infrastructure.event_bus import EventBus

    bus = EventBus()
    publisher = EventBusPublisher(bus)
    service = DummyService("planner")
    service.set_event_publisher(publisher)

    service.start()

    snapshot = bus.snapshot()
    assert snapshot.published == 1
    assert snapshot.accepted == 1
