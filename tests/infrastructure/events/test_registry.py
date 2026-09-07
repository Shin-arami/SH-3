from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

import pytest

from foundation.Enums.category import Category
from infrastructure.events.registry import (
    EventSchema,
    EventSchemaRegistry,
    SchemaKey,
)


def make_schema(
    identifier: str = "test.event",
    version: str = "1.0.0",
    owner: str = "test",
    category: Category = Category.RUNTIME,
    specification: str = "spec://test.event",
) -> EventSchema:
    return EventSchema(
        identifier=identifier,
        version=version,
        owner=owner,
        category=category,
        specification=specification,
    )


def test_schema_key_is_immutable() -> None:
    key = SchemaKey("test.event", "1.0.0")

    assert key.identifier == "test.event"
    assert key.version == "1.0.0"

    with pytest.raises(AttributeError):
        key.identifier = "other"  # type: ignore[misc]


def test_schema_key_rejects_empty_identifier() -> None:
    with pytest.raises(
        ValueError,
        match="schema identifier must not be empty"
    ):
        SchemaKey("", "1.0.0")


def test_schema_key_rejects_empty_version() -> None:
    with pytest.raises(
        ValueError,
        match="schema version must not be empty"
    ):
        SchemaKey("test.event", "")


def test_event_schema_validation() -> None:
    schema = make_schema()

    assert schema.identifier == "test.event"
    assert schema.version == "1.0.0"
    assert schema.owner == "test"
    assert schema.category is Category.RUNTIME
    assert schema.specification == "spec://test.event"
    assert schema.key == SchemaKey("test.event", "1.0.0")


@pytest.mark.parametrize(
    "kwargs, error",
    [
        ({"identifier": ""}, "schema identifier must not be empty"),
        ({"version": ""}, "schema version must not be empty"),
        ({"owner": ""}, "schema owner must not be empty"),
        ({"specification": ""}, "specification reference must not be empty"),
    ],
)
def test_event_schema_rejects_invalid_values(
    kwargs: dict[str, object],
    error: str,
) -> None:
    values: dict[str, object] = {
        "identifier": "test.event",
        "version": "1.0.0",
        "owner": "test",
        "category": Category.RUNTIME,
        "specification": "spec://test.event",
    }
    values.update(kwargs)

    with pytest.raises(
        ValueError,
        match=error
    ):
        EventSchema(**values)  # type: ignore[arg-type]


def test_event_schema_rejects_invalid_category() -> None:
    with pytest.raises(
        TypeError,
        match="category must be Category"
    ):
        EventSchema(
            identifier="test.event",
            version="1.0.0",
            owner="test",
            category="runtime",  # type: ignore[arg-type]
            specification="spec://test.event",
        )


def test_registry_starts_empty() -> None:
    registry = EventSchemaRegistry()

    assert registry.count() == 0
    assert registry.list() == ()
    assert not registry.contains("test.event")


def test_register_and_get() -> None:
    registry = EventSchemaRegistry()
    schema = make_schema()

    registry.register(schema)

    assert registry.count() == 1
    assert registry.contains("test.event")
    assert registry.contains("test.event", "1.0.0")
    assert registry.get("test.event") is schema
    assert registry.get("test.event", "1.0.0") is schema


def test_register_rejects_duplicate_without_replace() -> None:
    registry = EventSchemaRegistry()
    schema = make_schema()

    registry.register(schema)

    with pytest.raises(
        ValueError,
        match=re.escape("schema already registered: test.event@1.0.0")
    ):
        registry.register(schema)


def test_register_replace() -> None:
    registry = EventSchemaRegistry()
    first = make_schema(owner="first")
    second = make_schema(owner="second")

    registry.register(first)
    registry.register(second, replace=True)

    assert registry.count() == 1
    assert registry.get("test.event") is second
    assert registry.get("test.event").owner == "second"


def test_register_rejects_invalid_schema() -> None:
    registry = EventSchemaRegistry()

    with pytest.raises(
        TypeError,
        match="schema must be EventSchema"
    ):
        registry.register("invalid")  # type: ignore[arg-type]


def test_get_missing_schema() -> None:
    registry = EventSchemaRegistry()

    with pytest.raises(
        KeyError,
        match=re.escape("schema not registered: test.event")
    ):
        registry.get("test.event")


def test_get_missing_version() -> None:
    registry = EventSchemaRegistry()
    registry.register(make_schema())

    with pytest.raises(
        KeyError,
        match=re.escape("schema not registered: test.event@2.0.0")
    ):
        registry.get("test.event", "2.0.0")


def test_get_returns_latest_version() -> None:
    registry = EventSchemaRegistry()

    v1 = make_schema(version="1.0.0")
    v2 = make_schema(version="2.0.0")
    v10 = make_schema(version="10.0.0")

    registry.register(v1)
    registry.register(v10)
    registry.register(v2)

    assert registry.get("test.event") is v10


def test_get_latest_version_uses_numeric_order() -> None:
    registry = EventSchemaRegistry()

    v9 = make_schema(version="9.0.0")
    v10 = make_schema(version="10.0.0")

    registry.register(v9)
    registry.register(v10)

    assert registry.get("test.event") is v10


def test_list_returns_sorted_schemas() -> None:
    registry = EventSchemaRegistry()

    schemas = (
        make_schema(identifier="z.event", version="1.0.0"),
        make_schema(identifier="a.event", version="2.0.0"),
        make_schema(identifier="a.event", version="1.0.0"),
        make_schema(identifier="z.event", version="2.0.0"),
    )

    for schema in schemas:
        registry.register(schema)

    result = registry.list()

    assert [(schema.identifier, schema.version) for schema in result] == [
        ("a.event", "1.0.0"),
        ("a.event", "2.0.0"),
        ("z.event", "1.0.0"),
        ("z.event", "2.0.0"),
    ]


def test_list_filters_by_identifier() -> None:
    registry = EventSchemaRegistry()

    registry.register(make_schema("a.event", "1.0.0"))
    registry.register(make_schema("a.event", "2.0.0"))
    registry.register(make_schema("b.event", "1.0.0"))

    result = registry.list("a.event")

    assert [(schema.identifier, schema.version) for schema in result] == [
        ("a.event", "1.0.0"),
        ("a.event", "2.0.0"),
    ]


def test_unregister_returns_schema() -> None:
    registry = EventSchemaRegistry()
    schema = make_schema()

    registry.register(schema)

    removed = registry.unregister("test.event", "1.0.0")

    assert removed is schema
    assert registry.count() == 0
    assert not registry.contains("test.event", "1.0.0")


def test_unregister_missing_schema() -> None:
    registry = EventSchemaRegistry()

    with pytest.raises(
        KeyError,
        match=re.escape("schema not registered: test.event@1.0.0")
    ):
        registry.unregister("test.event", "1.0.0")


def test_clear_removes_all_schemas() -> None:
    registry = EventSchemaRegistry()

    registry.register(make_schema("a.event", "1.0.0"))
    registry.register(make_schema("b.event", "1.0.0"))

    registry.clear()

    assert registry.count() == 0
    assert registry.list() == ()


def test_validate_reference() -> None:
    registry = EventSchemaRegistry()
    registry.register(make_schema())

    assert registry.validate_reference("test.event", "1.0.0")
    assert not registry.validate_reference("test.event", "2.0.0")
    assert not registry.validate_reference("missing.event", "1.0.0")


def test_registry_is_thread_safe() -> None:
    registry = EventSchemaRegistry()

    schemas = [
        make_schema(
            identifier=f"event.{index}",
            version="1.0.0",
        )
        for index in range(100)
    ]

    def register(schema: EventSchema) -> None:
        registry.register(schema)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(register, schemas))

    assert registry.count() == 100

    for schema in schemas:
        assert registry.contains(schema.identifier, schema.version)
        assert registry.get(schema.identifier, schema.version) is schema


def test_registry_supports_multiple_versions_concurrently() -> None:
    registry = EventSchemaRegistry()

    schemas = [
        make_schema(
            identifier="test.event",
            version=f"{major}.0.0",
        )
        for major in range(1, 21)
    ]

    def register(schema: EventSchema) -> None:
        registry.register(schema)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(register, schemas))

    assert registry.count() == 20
    assert registry.get("test.event").version == "20.0.0"


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("1.0.0", (1, 0, 0, "0")),
        ("2.5.10", (2, 5, 10, "10")),
        ("10.0.0", (10, 0, 0, "0")),
        ("1.2", (1, 2, 0, "")),
        ("1", (1, 0, 0, "")),
        ("invalid", (0, 0, 0, "")),
    ],
)
def test_version_key(
    version: str,
    expected: tuple[int, int, int, str],
) -> None:
    assert EventSchemaRegistry._version_key(version) == expected
