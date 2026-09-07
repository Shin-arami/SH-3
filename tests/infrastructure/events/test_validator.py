from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest

from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.Enums.priority import Priority
from infrastructure.events.model import Event, EventContext, EventMetadata
from infrastructure.events.validator import (
    EventValidationError,
    EventValidator,
    ValidationIssue,
)


def mutable_dict(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value)


def make_metadata(
    *,
    event_id: str = "ent_20260819000000_12345678",
    event_name: str = "test.event",
    event_version: str = "1.0.0",
    timestamp: datetime | None = None,
    producer: str = "test",
    correlation_id: str = "ent_20260819000000_abcdefgh",
    causation_id: str | None = None,
    priority: Priority = Priority.NORMAL,
    tags: dict[str, str] | None = None,
    trace_id: str | None = None,
    tenant_id: str | None = None,
) -> EventMetadata:
    return EventMetadata(
        event_id=event_id,
        event_name=event_name,
        event_version=event_version,
        timestamp=timestamp or datetime.now(UTC),
        producer=producer,
        correlation_id=correlation_id,
        causation_id=causation_id,
        priority=priority,
        tags=tags or {},
        trace_id=trace_id,
        tenant_id=tenant_id,
    )


def make_event(
    *,
    metadata: EventMetadata | None = None,
    payload: dict[str, object] | None = None,
    context: EventContext | None = None,
    category: Category = Category.RUNTIME,
    event_type: EventType = EventType.EXECUTE,
) -> Event:
    return Event(
        metadata=metadata or make_metadata(),
        payload=payload or {"value": 42},
        context=context or EventContext(),
        category=category,
        event_type=event_type,
    )


def make_event_dict() -> dict[str, object]:
    return make_event().to_dict()


def test_validation_issue_fields() -> None:
    issue = ValidationIssue(
        field="metadata.event_id",
        message="must not be empty",
        value="",
    )

    assert issue.field == "metadata.event_id"
    assert issue.message == "must not be empty"
    assert issue.value == ""
    assert str(issue) == "metadata.event_id: must not be empty"


def test_validation_issue_default_value() -> None:
    issue = ValidationIssue(
        field="payload",
        message="must be a mapping",
    )

    assert issue.value is None


def test_valid_event_passes_validation() -> None:
    event = make_event()

    EventValidator.validate(event)

    assert EventValidator.is_valid(event)
    assert EventValidator.collect(event) == []


def test_valid_event_with_full_metadata_passes() -> None:
    metadata = make_metadata(
        causation_id="ent_20260819000000_causation",
        priority=Priority.HIGH,
        tags={"source": "test", "environment": "unit"},
        trace_id="trc_20260819000000_trace1234",
        tenant_id="tenant-1",
    )

    event = make_event(metadata=metadata)

    assert EventValidator.is_valid(event)
    EventValidator.validate(event)


def test_valid_event_with_full_context_passes() -> None:
    context = EventContext(
        runtime={"runtime": "test"},
        execution={"attempt": 1},
        mission={"mission_id": "mission-1"},
        security={"authenticated": True},
        tracing={"span_id": "span-1"},
    )

    event = make_event(context=context)

    assert EventValidator.is_valid(event)


def test_non_event_is_invalid() -> None:
    value = object()

    assert not EventValidator.is_valid(value)  # type: ignore[arg-type]

    issues = EventValidator.collect(value)  # type: ignore[arg-type]

    assert len(issues) == 1
    assert issues[0].field == "event"
    assert issues[0].message == "must be an Event instance"


def test_non_event_raises_event_validation_error() -> None:
    with pytest.raises(EventValidationError) as exc_info:
        EventValidator.validate(object())  # type: ignore[arg-type]

    assert len(exc_info.value.issues) == 1
    assert exc_info.value.issues[0].field == "event"


@pytest.mark.parametrize(
    "field",
    [
        "event_id",
        "event_name",
        "event_version",
        "producer",
        "correlation_id",
    ],
)
def test_empty_required_metadata_field_is_invalid(field: str) -> None:
    data = make_event_dict()
    metadata = mutable_dict(data["metadata"])
    metadata[field] = ""
    data["metadata"] = metadata

    issues = EventValidator.collect_dict(data)

    assert any(
        issue.field == f"metadata.{field}" and issue.message == "must not be empty"
        for issue in issues
    )


@pytest.mark.parametrize(
    "field",
    [
        "event_id",
        "event_name",
        "event_version",
        "producer",
        "correlation_id",
    ],
)


def test_missing_required_metadata_field_in_dict_is_invalid(field: str) -> None:
    data = make_event_dict()
    metadata = dict(cast(dict[str, Any], data["metadata"]))
    del metadata[field]
    data["metadata"] = metadata

    issues = EventValidator.collect_dict(data)

    assert any(
        issue.field == f"metadata.{field}" and issue.message == "required field is missing"
        for issue in issues
    )


def test_missing_top_level_fields_are_reported() -> None:
    issues = EventValidator.collect_dict({})

    assert {issue.field for issue in issues} == {
        "metadata",
        "payload",
        "context",
    }


def test_missing_metadata_is_reported() -> None:
    data = make_event_dict()
    del data["metadata"]

    issues = EventValidator.collect_dict(data)

    assert any(
        issue.field == "metadata" and issue.message == "required field is missing"
        for issue in issues
    )


def test_missing_payload_is_reported() -> None:
    data = make_event_dict()
    del data["payload"]

    issues = EventValidator.collect_dict(data)

    assert any(
        issue.field == "payload" and issue.message == "required field is missing"
        for issue in issues
    )


def test_missing_context_is_reported() -> None:
    data = make_event_dict()
    del data["context"]

    issues = EventValidator.collect_dict(data)

    assert any(
        issue.field == "context" and issue.message == "required field is missing"
        for issue in issues
    )


def test_invalid_metadata_object_is_reported() -> None:
    event = object.__new__(Event)
    object.__setattr__(event, "metadata", "invalid")
    object.__setattr__(event, "payload", {})
    object.__setattr__(event, "context", EventContext())
    object.__setattr__(event, "category", Category.RUNTIME)
    object.__setattr__(event, "event_type", EventType.UNKNOWN)

    issues = EventValidator.collect(event)

    assert any(
        issue.field == "metadata" and issue.message == "must be EventMetadata" for issue in issues
    )


def test_invalid_context_object_is_reported() -> None:
    event = object.__new__(Event)
    object.__setattr__(event, "metadata", make_metadata())
    object.__setattr__(event, "payload", {})
    object.__setattr__(event, "context", "invalid")
    object.__setattr__(event, "category", Category.RUNTIME)
    object.__setattr__(event, "event_type", EventType.UNKNOWN)

    issues = EventValidator.collect(event)

    assert any(
        issue.field == "context" and issue.message == "must be EventContext" for issue in issues
    )


def test_invalid_payload_is_reported() -> None:
    event = object.__new__(Event)
    object.__setattr__(event, "metadata", make_metadata())
    object.__setattr__(event, "payload", "invalid")
    object.__setattr__(event, "context", EventContext())
    object.__setattr__(event, "category", Category.RUNTIME)
    object.__setattr__(event, "event_type", EventType.UNKNOWN)

    issues = EventValidator.collect(event)

    assert any(
        issue.field == "payload" and issue.message == "must be a mapping" for issue in issues
    )


@pytest.mark.parametrize(
    "payload",
    [
        None,
        1,
        "payload",
        [],
        object(),
    ],
)
def test_invalid_payload_dict_is_reported(payload: object) -> None:
    data = make_event_dict()
    data["payload"] = payload

    issues = EventValidator.collect_dict(data)

    assert any(
        issue.field == "payload" and issue.message == "must be a mapping" for issue in issues
    )


def test_valid_payload_dict_passes() -> None:
    data = make_event_dict()

    assert EventValidator.is_valid_dict(data)
    EventValidator.validate_dict(data)


def test_invalid_context_field_is_reported() -> None:
    data = make_event_dict()
    context = dict(cast(dict[str, Any], data["context"]))
    context["runtime"] = "invalid"
    data["context"] = context

    issues = EventValidator.collect_dict(data)

    assert any(
        issue.field == "context.runtime" and issue.message == "must be a mapping"
        for issue in issues
    )


def test_multiple_invalid_context_fields_are_reported() -> None:
    data = make_event_dict()
    context = dict(cast(dict[str, Any], data["context"]))
    context["runtime"] = "invalid"
    context["execution"] = 123
    context["security"] = []
    data["context"] = context

    issues = EventValidator.collect_dict(data)

    fields = {issue.field for issue in issues}

    assert "context.runtime" in fields
    assert "context.execution" in fields
    assert "context.security" in fields


def test_invalid_context_object_in_dict_is_reported() -> None:
    data = make_event_dict()
    data["context"] = "invalid"

    issues = EventValidator.collect_dict(data)

    assert any(
        issue.field == "context" and issue.message == "must be a mapping" for issue in issues
    )


@pytest.mark.parametrize(
    "category",
    [
        "invalid",
        "RUNTIME",
        "",
        None,
        123,
    ],
)
def test_invalid_category_dict_is_reported(category: object) -> None:
    data = make_event_dict()
    data["category"] = category

    issues = EventValidator.collect_dict(data)

    assert any(
        issue.field == "category" and issue.message == "invalid category" for issue in issues
    )


def test_valid_category_dict_passes() -> None:
    data = make_event_dict()
    data["category"] = Category.MEMORY.value

    assert EventValidator.is_valid_dict(data)


def test_invalid_category_object_is_reported() -> None:
    event = object.__new__(Event)
    object.__setattr__(event, "metadata", make_metadata())
    object.__setattr__(event, "payload", {})
    object.__setattr__(event, "context", EventContext())
    object.__setattr__(event, "category", "invalid")
    object.__setattr__(event, "event_type", EventType.UNKNOWN)

    issues = EventValidator.collect(event)

    assert any(
        issue.field == "category" and issue.message == "must be Category" for issue in issues
    )


@pytest.mark.parametrize(
    "event_type",
    [
        "invalid",
        "EXECUTE",
        "",
        None,
        123,
    ],
)
def test_invalid_event_type_dict_is_reported(event_type: object) -> None:
    data = make_event_dict()
    data["event_type"] = event_type

    issues = EventValidator.collect_dict(data)

    assert any(
        issue.field == "event_type" and issue.message == "invalid event type" for issue in issues
    )


def test_valid_event_type_dict_passes() -> None:
    data = make_event_dict()
    data["event_type"] = EventType.COMPLETE.value

    assert EventValidator.is_valid_dict(data)


def test_invalid_event_type_object_is_reported() -> None:
    event = object.__new__(Event)
    object.__setattr__(event, "metadata", make_metadata())
    object.__setattr__(event, "payload", {})
    object.__setattr__(event, "context", EventContext())
    object.__setattr__(event, "category", Category.RUNTIME)
    object.__setattr__(event, "event_type", "invalid")

    issues = EventValidator.collect(event)

    assert any(
        issue.field == "event_type" and issue.message == "must be EventType" for issue in issues
    )


@pytest.mark.parametrize(
    "timestamp",
    [
        123,
        object(),
        [],
        {},
    ],
)
def test_invalid_timestamp_dict_is_reported(timestamp: object) -> None:
    data = make_event_dict()
    metadata = mutable_dict(data["metadata"])
    metadata["timestamp"] = timestamp
    data["metadata"] = metadata

    issues = EventValidator.collect_dict(data)

    assert any(
        issue.field == "metadata.timestamp" and issue.message == "must be datetime or ISO timestamp"
        for issue in issues
    )


@pytest.mark.parametrize(
    "timestamp",
    [
        datetime.now(UTC),
        "2026-08-19T00:00:00+00:00",
    ],
)
def test_valid_timestamp_dict_passes(timestamp: datetime | str) -> None:
    data = make_event_dict()
    metadata = mutable_dict(data["metadata"])
    metadata["timestamp"] = timestamp
    data["metadata"] = metadata

    issues = EventValidator.collect_dict(data)

    assert not any(issue.field == "metadata.timestamp" for issue in issues)


@pytest.mark.parametrize(
    "priority",
    [
        Priority.LOW,
        Priority.NORMAL,
        Priority.HIGH,
        Priority.REALTIME,
        "LOW",
        "NORMAL",
        "CRITICAL",
    ],
)
def test_valid_priority_dict_passes(priority: Priority | str) -> None:
    data = make_event_dict()
    metadata = mutable_dict(data["metadata"])
    metadata["priority"] = priority
    data["metadata"] = metadata

    issues = EventValidator.collect_dict(data)

    assert not any(issue.field == "metadata.priority" for issue in issues)


@pytest.mark.parametrize(
    "priority",
    [
        "INVALID",
        "",
        1,
        50.0,
        object(),
    ],
)
def test_invalid_priority_dict_is_reported(priority: object) -> None:
    data = make_event_dict()
    metadata = mutable_dict(data["metadata"])
    metadata["priority"] = priority
    data["metadata"] = metadata

    issues = EventValidator.collect_dict(data)

    assert any(issue.field == "metadata.priority" for issue in issues)


@pytest.mark.parametrize(
    "field",
    [
        "causation_id",
        "trace_id",
        "tenant_id",
    ],
)
def test_optional_string_fields_must_be_strings(field: str) -> None:
    data = make_event_dict()
    metadata = mutable_dict(data["metadata"])
    metadata[field] = 123
    data["metadata"] = metadata

    issues = EventValidator.collect_dict(data)

    assert any(
        issue.field == f"metadata.{field}" and issue.message == "must be a string"
        for issue in issues
    )


@pytest.mark.parametrize(
    "field",
    [
        "causation_id",
        "trace_id",
        "tenant_id",
    ],
)
def test_optional_string_fields_accept_none(field: str) -> None:
    data = make_event_dict()
    metadata = mutable_dict(data["metadata"])
    metadata[field] = None
    data["metadata"] = metadata

    issues = EventValidator.collect_dict(data)

    assert not any(issue.field == f"metadata.{field}" for issue in issues)


def test_valid_tags_pass() -> None:
    data = make_event_dict()
    metadata = mutable_dict(data["metadata"])
    metadata["tags"] = {
        "source": "test",
        "environment": "unit",
    }
    data["metadata"] = metadata

    assert EventValidator.is_valid_dict(data)


def test_invalid_tags_type_is_reported() -> None:
    data = make_event_dict()
    metadata = mutable_dict(data["metadata"])
    metadata["tags"] = "invalid"
    data["metadata"] = metadata

    issues = EventValidator.collect_dict(data)

    assert any(
        issue.field == "metadata.tags" and issue.message == "must be a mapping" for issue in issues
    )


def test_invalid_tag_key_is_reported() -> None:
    data = make_event_dict()
    metadata = mutable_dict(data["metadata"])
    metadata["tags"] = {
        "": "value",
    }
    data["metadata"] = metadata

    issues = EventValidator.collect_dict(data)

    assert any(
        issue.field == "metadata.tags" and issue.message == "tag keys must be non-empty strings"
        for issue in issues
    )


def test_invalid_tag_key_type_is_reported() -> None:
    data = make_event_dict()
    metadata = mutable_dict(data["metadata"])
    metadata["tags"] = {
        1: "value",
    }
    data["metadata"] = metadata

    issues = EventValidator.collect_dict(data)

    assert any(
        issue.field == "metadata.tags" and issue.message == "tag keys must be non-empty strings"
        for issue in issues
    )


def test_invalid_tag_value_type_is_reported() -> None:
    data = make_event_dict()
    metadata = mutable_dict(data["metadata"])
    metadata["tags"] = {
        "key": 123,
    }
    data["metadata"] = metadata

    issues = EventValidator.collect_dict(data)

    assert any(
        issue.field == "metadata.tags" and issue.message == "tag values must be strings"
        for issue in issues
    )


def test_multiple_tag_issues_are_collected() -> None:
    data = make_event_dict()
    metadata = mutable_dict(data["metadata"])
    metadata["tags"] = {
        "": 123,
        1: "invalid-key",
    }
    data["metadata"] = metadata

    issues = EventValidator.collect_dict(data)

    messages = [issue.message for issue in issues if issue.field == "metadata.tags"]

    assert messages.count("tag keys must be non-empty strings") == 2
    assert messages.count("tag values must be strings") == 1


def test_non_mapping_dict_input_is_invalid() -> None:
    value = object()

    assert not EventValidator.is_valid_dict(value)  # type: ignore[arg-type]

    issues = EventValidator.collect_dict(value)  # type: ignore[arg-type]

    assert len(issues) == 1
    assert issues[0].field == "event"
    assert issues[0].message == "must be a mapping"


def test_validate_dict_raises_for_invalid_input() -> None:
    with pytest.raises(EventValidationError) as exc_info:
        EventValidator.validate_dict({})

    assert exc_info.value.issues
    assert "metadata: required field is missing" in str(exc_info.value)


def test_validation_error_contains_all_issues() -> None:
    data = make_event_dict()
    del data["metadata"]
    data["payload"] = []
    data["context"] = "invalid"
    data["category"] = "invalid"
    data["event_type"] = "invalid"

    with pytest.raises(EventValidationError) as exc_info:
        EventValidator.validate_dict(data)

    error = exc_info.value

    assert len(error.issues) >= 5
    assert "metadata: required field is missing" in str(error)
    assert "payload: must be a mapping" in str(error)
    assert "context: must be a mapping" in str(error)
    assert "category: invalid category" in str(error)
    assert "event_type: invalid event type" in str(error)


def test_is_valid_dict_returns_false_for_invalid_dict() -> None:
    data = make_event_dict()
    data["payload"] = []

    assert not EventValidator.is_valid_dict(data)


def test_collect_does_not_raise_for_invalid_event_structure() -> None:
    event = object.__new__(Event)
    object.__setattr__(event, "metadata", "invalid")
    object.__setattr__(event, "payload", "invalid")
    object.__setattr__(event, "context", "invalid")
    object.__setattr__(event, "category", "invalid")
    object.__setattr__(event, "event_type", "invalid")

    issues = EventValidator.collect(event)

    assert len(issues) == 5
    assert {issue.field for issue in issues} == {
        "metadata",
        "payload",
        "context",
        "category",
        "event_type",
    }


def test_collect_dict_collects_multiple_independent_errors() -> None:
    data = {
        "metadata": {
            "event_id": "",
            "event_name": 123,
            "event_version": "",
            "timestamp": 123,
            "producer": "",
            "correlation_id": None,
            "priority": "INVALID",
            "tags": "INVALID",
            "causation_id": 1,
            "trace_id": 2,
            "tenant_id": 3,
        },
        "payload": [],
        "context": {
            "runtime": "INVALID",
            "execution": 123,
        },
        "category": "INVALID",
        "event_type": "INVALID",
    }

    issues = EventValidator.collect_dict(data)

    assert len(issues) >= 15
    assert all(isinstance(issue, ValidationIssue) for issue in issues)


def test_event_validation_error_is_value_error() -> None:
    error = EventValidationError(
        (
            ValidationIssue(
                "event",
                "invalid",
            ),
        )
    )

    assert isinstance(error, ValueError)
    assert error.issues[0].field == "event"
    assert str(error) == "event: invalid"
