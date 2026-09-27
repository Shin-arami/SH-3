from __future__ import annotations

import pytest

from infrastructure.events import Event, EventPropagationContext
from infrastructure.events.model import EventContext


def test_create_preserves_context() -> None:
    context = EventPropagationContext.create(
        "correlation-1",
        trace_id="trace-1",
        tenant_id="tenant-1",
    )

    assert context.correlation_id == "correlation-1"
    assert context.causation_id is None
    assert context.trace_id == "trace-1"
    assert context.tenant_id == "tenant-1"


def test_from_event_creates_child_context() -> None:
    event = Event.create(
        event_name="TestEvent",
        producer="test",
        correlation_id="correlation-1",
        causation_id="parent-1",
        trace_id="trace-1",
        tenant_id="tenant-1",
        context=EventContext(),
    )

    context = EventPropagationContext.from_event(event)

    assert context.correlation_id == "correlation-1"
    assert context.causation_id == event.metadata.event_id
    assert context.trace_id == "trace-1"
    assert context.tenant_id == "tenant-1"


def test_next_updates_causation_only() -> None:
    context = EventPropagationContext.create(
        "correlation-1",
        causation_id="event-1",
        trace_id="trace-1",
        tenant_id="tenant-1",
    )

    next_context = context.next("event-2")

    assert next_context.correlation_id == "correlation-1"
    assert next_context.causation_id == "event-2"
    assert next_context.trace_id == "trace-1"
    assert next_context.tenant_id == "tenant-1"
    assert context.causation_id == "event-1"


def test_to_event_kwargs_omits_none_values() -> None:
    context = EventPropagationContext.create(
        "correlation-1",
        trace_id="trace-1",
    )

    assert context.to_event_kwargs() == {
        "correlation_id": "correlation-1",
        "trace_id": "trace-1",
    }


def test_from_metadata_creates_child_context() -> None:
    context = EventPropagationContext.from_metadata(
        correlation_id="correlation-1",
        event_id="event-1",
        trace_id="trace-1",
    )

    assert context.correlation_id == "correlation-1"
    assert context.causation_id == "event-1"
    assert context.trace_id == "trace-1"
    assert context.tenant_id is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"correlation_id": ""},
        {"correlation_id": "c", "causation_id": ""},
        {"correlation_id": "c", "trace_id": ""},
        {"correlation_id": "c", "tenant_id": ""},
    ],
)
def test_rejects_empty_identifiers(kwargs: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        EventPropagationContext(**kwargs)


def test_rejects_invalid_event() -> None:
    with pytest.raises(TypeError):
        EventPropagationContext.from_event(object())  # type: ignore[arg-type]


def test_rejects_empty_event_id() -> None:
    context = EventPropagationContext.create("correlation-1")

    with pytest.raises(ValueError):
        context.next("")
