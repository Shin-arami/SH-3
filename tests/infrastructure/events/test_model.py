from datetime import UTC, datetime
from types import MappingProxyType

import pytest

from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.Enums.priority import Priority
from infrastructure.events.model import Event, EventContext, EventMetadata


def create_metadata() -> EventMetadata:
    return EventMetadata(
        event_id="ent_20260819000000_12345678",
        event_name="test.event",
        event_version="1.0.0",
        timestamp=datetime(2026, 8, 19, tzinfo=UTC),
        producer="test",
        correlation_id="corr-001",
        priority=Priority.NORMAL,
        tags={"source": "test"},
    )


def create_event() -> Event:
    return Event(
        metadata=create_metadata(),
        payload={"value": 42},
        context=EventContext(
            runtime={"mode": "test"},
            execution={"step": 1},
        ),
        category=Category.RUNTIME,
        event_type=EventType.CREATED,
    )


def test_metadata_is_immutable() -> None:
    metadata = create_metadata()
    with pytest.raises(AttributeError):
        metadata.event_name = "changed"  # type: ignore[misc]


def test_metadata_tags_are_immutable() -> None:
    metadata = create_metadata()
    assert isinstance(metadata.tags, MappingProxyType)
    with pytest.raises(TypeError):
        metadata.tags["new"] = "value"  # type: ignore[index]


def test_metadata_to_dict_and_from_dict_round_trip() -> None:
    metadata = create_metadata()
    restored = EventMetadata.from_dict(metadata.to_dict())
    assert restored == metadata
    assert restored.to_dict() == metadata.to_dict()


def test_context_mappings_are_immutable() -> None:
    context = EventContext(runtime={"mode": "test"})
    assert isinstance(context.runtime, MappingProxyType)
    with pytest.raises(TypeError):
        context.runtime["mode"] = "changed"  # type: ignore[index]


def test_context_round_trip() -> None:
    context = EventContext(
        runtime={"mode": "test"},
        execution={"step": 1},
        mission={"id": "mission-1"},
        security={"level": "normal"},
        tracing={"trace": "trace-1"},
    )
    restored = EventContext.from_dict(context.to_dict())
    assert restored == context
    assert restored.to_dict() == context.to_dict()


def test_event_is_immutable() -> None:
    event = create_event()
    with pytest.raises(AttributeError):
        event.category = Category.EVENT  # type: ignore[misc]


def test_event_payload_is_immutable() -> None:
    event = create_event()
    assert isinstance(event.payload, MappingProxyType)
    with pytest.raises(TypeError):
        event.payload["new"] = "value"  # type: ignore[index]


def test_event_properties() -> None:
    event = create_event()
    assert event.id == event.metadata.event_id
    assert event.name == "test.event"
    assert event.version == "1.0.0"
    assert event.priority is Priority.NORMAL
    assert event.correlation_id == "corr-001"
    assert event.trace_id is None
    assert event.causation_id is None
    assert event.timestamp.tzinfo is not None


def test_event_round_trip() -> None:
    event = create_event()
    restored = Event.from_dict(event.to_dict())
    assert restored == event
    assert restored.to_dict() == event.to_dict()


def test_event_create() -> None:
    event = Event.create(
        event_name="test.created",
        producer="test",
        payload={"value": 1},
        category=Category.RUNTIME,
        event_type=EventType.CREATED,
    )
    assert event.id
    assert event.name == "test.created"
    assert event.version == "1.0.0"
    assert event.metadata.producer == "test"
    assert event.correlation_id == event.id
    assert event.timestamp.tzinfo is not None
    assert event.payload["value"] == 1


def test_metadata_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        EventMetadata(
            event_id="event-1",
            event_name="test",
            event_version="1.0.0",
            timestamp=datetime(2026, 8, 19),
            producer="test",
            correlation_id="corr-1",
        )


def test_metadata_rejects_empty_required_values() -> None:
    with pytest.raises(ValueError, match="event_name"):
        EventMetadata(
            event_id="event-1",
            event_name="",
            event_version="1.0.0",
            timestamp=datetime(2026, 8, 19, tzinfo=UTC),
            producer="test",
            correlation_id="corr-1",
        )


def test_event_rejects_invalid_category() -> None:
    metadata = create_metadata()
    with pytest.raises(TypeError, match="category"):
        Event(
            metadata=metadata,
            payload={},
            context=EventContext(),
            category="runtime",  # type: ignore[arg-type]
        )


def test_event_rejects_invalid_event_type() -> None:
    metadata = create_metadata()
    with pytest.raises(TypeError, match="event_type"):
        Event(
            metadata=metadata,
            payload={},
            context=EventContext(),
            event_type="created",  # type: ignore[arg-type]
        )
