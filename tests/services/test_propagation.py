from __future__ import annotations

from itertools import pairwise
from typing import Any

import pytest

from foundation.enums import LifecycleState
from foundation.Enums.event import EventType
from infrastructure.event_bus import PublishResult
from infrastructure.events import Event, EventPropagationContext
from services.base import Service, ServiceException


class DummyService(Service):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__("test-service", **kwargs)

    def _on_start(self) -> None:
        pass


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def publish(self, event: Event) -> PublishResult:
        self.events.append(event)
        return PublishResult(
            event_id=event.metadata.event_id,
            accepted=True,
            queued=False,
            delivered=True,
        )


class FailingPublisher:
    def publish(self, event: Event) -> PublishResult:
        raise RuntimeError("publisher failure")


def test_start_propagates_context() -> None:
    publisher = RecordingPublisher()
    service = DummyService(event_publisher=publisher)
    context = EventPropagationContext.create(
        "workflow-001",
        trace_id="trace-001",
        tenant_id="tenant-001",
    )

    service.start(context=context)

    assert len(publisher.events) == 1
    event = publisher.events[0]
    assert event.name == "ServiceStarted"
    assert event.event_type is EventType.START
    assert event.metadata.correlation_id == "workflow-001"
    assert event.metadata.causation_id is None
    assert event.metadata.trace_id == "trace-001"
    assert event.metadata.tenant_id == "tenant-001"


def test_lifecycle_events_form_causation_chain() -> None:
    publisher = RecordingPublisher()
    service = DummyService(event_publisher=publisher)
    context = EventPropagationContext.create(
        "workflow-002",
        trace_id="trace-002",
        tenant_id="tenant-002",
    )

    service.start(context=context)
    service.suspend()
    service.resume()
    service.terminate()

    assert [event.name for event in publisher.events] == [
        "ServiceStarted",
        "ServiceSuspended",
        "ServiceResumed",
        "ServiceStopped",
    ]

    events = publisher.events
    assert all(event.metadata.correlation_id == "workflow-002" for event in events)
    assert all(event.metadata.trace_id == "trace-002" for event in events)
    assert all(event.metadata.tenant_id == "tenant-002" for event in events)

    assert events[0].metadata.causation_id is None
    for previous, current in pairwise(events):
        assert current.metadata.causation_id == previous.metadata.event_id


def test_failed_lifecycle_preserves_propagation() -> None:
    publisher = RecordingPublisher()

    class BrokenService(DummyService):
        def _on_start(self) -> None:
            raise RuntimeError("start failure")

    service = BrokenService(event_publisher=publisher)
    context = EventPropagationContext.create(
        "workflow-003",
        trace_id="trace-003",
        tenant_id="tenant-003",
    )

    with pytest.raises(ServiceException, match="Service start failed"):
        service.start(context=context)

    assert len(publisher.events) == 1
    event = publisher.events[0]
    assert event.name == "ServiceFailed"
    assert event.metadata.correlation_id == "workflow-003"
    assert event.metadata.trace_id == "trace-003"
    assert event.metadata.tenant_id == "tenant-003"


def test_context_can_be_replaced_for_new_operation() -> None:
    publisher = RecordingPublisher()
    service = DummyService(event_publisher=publisher)

    first = EventPropagationContext.create("workflow-004", trace_id="trace-004")
    second = EventPropagationContext.create("workflow-005", trace_id="trace-005")

    service.start(context=first)
    service.suspend(context=second)

    assert publisher.events[0].metadata.correlation_id == "workflow-004"
    assert publisher.events[0].metadata.trace_id == "trace-004"
    assert publisher.events[1].metadata.correlation_id == "workflow-005"
    assert publisher.events[1].metadata.trace_id == "trace-005"


def test_publisher_failure_does_not_break_service() -> None:
    service = DummyService(event_publisher=FailingPublisher())
    context = EventPropagationContext.create("workflow-006")

    service.start(context=context)

    assert service.state is LifecycleState.ACTIVE
    assert service.propagation_context is not None
    assert service.propagation_context.correlation_id == "workflow-006"


def test_no_publisher_preserves_existing_api() -> None:
    service = DummyService()

    service.start()

    assert service.state is LifecycleState.ACTIVE
    assert service.active is True


def test_invalid_context_is_rejected() -> None:
    service = DummyService()

    with pytest.raises(TypeError, match="EventPropagationContext"):
        service.start(context="invalid")  # type: ignore[arg-type]


def test_propagation_context_is_immutable() -> None:
    context = EventPropagationContext.create(
        "workflow-007",
        trace_id="trace-007",
        tenant_id="tenant-007",
    )

    with pytest.raises(AttributeError):
        context.correlation_id = "changed"  # type: ignore[misc]
