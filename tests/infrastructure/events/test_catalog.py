from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from infrastructure.events import (
    CANONICAL_EVENT_VERSION,
    CanonicalEventCatalog,
    Event,
    EventDefinition,
)


def test_canonical_catalog_contains_required_events() -> None:
    catalog = CanonicalEventCatalog()
    names = {definition.name for definition in catalog.all()}
    assert "ComponentStarted" in names
    assert "RuntimeExecutionCompleted" in names
    assert "LearningResultRecorded" in names
    assert "RecoveryCompleted" in names
    assert "OptimizationCompleted" in names
    assert "DeploymentCompleted" in names


def test_canonical_event_definition_is_immutable() -> None:
    definition = EventDefinition(
        name="TestEvent",
        version="1.0.0",
        category=Category.EVENT,
        event_type=EventType.CREATED,
        required_payload=("id",),
        optional_payload=("value",),
        producer="test",
        description="test event",
    )
    with pytest.raises(AttributeError):
        definition.name = "Changed"  # type: ignore[misc]


def test_duplicate_registration_is_rejected() -> None:
    catalog = CanonicalEventCatalog(definitions=())
    definition = EventDefinition(
        name="TestEvent",
        version="1.0.0",
        category=Category.EVENT,
        event_type=EventType.CREATED,
        required_payload=("id",),
        optional_payload=(),
        producer="test",
        description="test event",
    )
    catalog.register(definition)
    with pytest.raises(ValueError, match="already registered"):
        catalog.register(definition)


def test_replace_is_explicit() -> None:
    catalog = CanonicalEventCatalog(definitions=())
    first = EventDefinition(
        name="TestEvent",
        version="1.0.0",
        category=Category.EVENT,
        event_type=EventType.CREATED,
        required_payload=("id",),
        optional_payload=(),
        producer="test",
        description="first",
    )
    second = EventDefinition(
        name="TestEvent",
        version="1.0.0",
        category=Category.EVENT,
        event_type=EventType.CREATED,
        required_payload=("id", "value"),
        optional_payload=(),
        producer="test",
        description="second",
    )
    catalog.register(first)
    catalog.register(second, replace=True)
    assert catalog.get("TestEvent").description == "second"


def test_lookup_is_deterministic() -> None:
    catalog = CanonicalEventCatalog()
    definitions = catalog.all()
    assert definitions == tuple(
        sorted(
            definitions,
            key=lambda item: (item.name, _version_key(item.version)),
        )
    )


def test_default_version_is_canonical() -> None:
    catalog = CanonicalEventCatalog()
    definition = catalog.require("ComponentStarted")
    assert definition.version == CANONICAL_EVENT_VERSION


def test_payload_contract_rejects_missing_required_field() -> None:
    catalog = CanonicalEventCatalog()
    event = Event.create(
        event_name="RuntimeExecutionCompleted",
        producer="runtime",
        category=Category.EXECUTION,
        event_type=EventType.COMPLETE,
        payload={
            "execution_id": "exec-1",
            "component": "runtime",
            "result": "ok",
            "success": True,
        },
    )
    with pytest.raises(ValueError, match="missing payload fields"):
        catalog.validate(event)


def test_payload_contract_rejects_unknown_field() -> None:
    catalog = CanonicalEventCatalog()
    event = Event.create(
        event_name="RuntimeExecutionCompleted",
        producer="runtime",
        category=Category.EXECUTION,
        event_type=EventType.COMPLETE,
        payload={
            "execution_id": "exec-1",
            "component": "runtime",
            "result": "ok",
            "duration_ms": 10,
            "success": True,
            "unexpected": True,
        },
    )
    with pytest.raises(ValueError, match="unknown payload fields"):
        catalog.validate(event)


def test_event_contract_validation_succeeds() -> None:
    catalog = CanonicalEventCatalog()
    event = Event.create(
        event_name="RuntimeExecutionCompleted",
        producer="runtime",
        category=Category.EXECUTION,
        event_type=EventType.COMPLETE,
        payload={
            "execution_id": "exec-1",
            "component": "runtime",
            "result": "ok",
            "duration_ms": 10,
            "success": True,
        },
    )
    catalog.validate(event)


def test_event_contract_rejects_metadata_mismatch() -> None:
    catalog = CanonicalEventCatalog()
    event = Event.create(
        event_name="RuntimeExecutionCompleted",
        producer="kernel",
        category=Category.EXECUTION,
        event_type=EventType.COMPLETE,
        payload={
            "execution_id": "exec-1",
            "component": "runtime",
            "result": "ok",
            "duration_ms": 10,
            "success": True,
        },
    )
    with pytest.raises(ValueError, match="producer mismatch"):
        catalog.validate(event)


def test_event_definition_rejects_overlapping_payload_fields() -> None:
    with pytest.raises(
        ValueError,
        match="must not overlap",
    ):
        EventDefinition(
            name="TestEvent",
            version="1.0.0",
            category=Category.EVENT,
            event_type=EventType.CREATED,
            required_payload=("id",),
            optional_payload=("id",),
            producer="test",
            description="test",
        )


def test_catalog_is_thread_safe() -> None:
    catalog = CanonicalEventCatalog(definitions=())

    def register(index: int) -> None:
        catalog.register(
            EventDefinition(
                name=f"TestEvent{index}",
                version="1.0.0",
                category=Category.EVENT,
                event_type=EventType.CREATED,
                required_payload=("id",),
                optional_payload=(),
                producer="test",
                description=f"test {index}",
            )
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(register, range(64)))

    assert catalog.count() == 64


def test_unregister_removes_definition() -> None:
    catalog = CanonicalEventCatalog(definitions=())
    definition = EventDefinition(
        name="TestEvent",
        version="1.0.0",
        category=Category.EVENT,
        event_type=EventType.CREATED,
        required_payload=(),
        optional_payload=(),
        producer="test",
        description="test",
    )
    catalog.register(definition)
    removed = catalog.unregister("TestEvent")
    assert removed == definition
    assert not catalog.contains("TestEvent")


def test_require_raises_for_unknown_event() -> None:
    catalog = CanonicalEventCatalog(definitions=())
    with pytest.raises(KeyError, match="not registered"):
        catalog.require("UnknownEvent")


def _version_key(version: str) -> tuple[int, int, int, str]:
    parts = version.split(".", 2)
    numbers: list[int] = []
    for part in parts[:3]:
        try:
            numbers.append(int(part))
        except ValueError:
            numbers.append(0)
    while len(numbers) < 3:
        numbers.append(0)
    suffix = parts[2] if len(parts) == 3 else ""
    return numbers[0], numbers[1], numbers[2], suffix
