from __future__ import annotations

import pytest

from infrastructure.storage.model import (
    StorageQuery,
    StorageRecord,
    StorageResult,
)


def test_storage_record_creation() -> None:
    record = StorageRecord.create(
        "id-1",
        "knowledge",
        "1.0",
        {"value": 42},
        metadata={"source": "test"},
        timestamp="2026-01-01T00:00:00+00:00",
    )

    assert record.identifier == "id-1"
    assert record.type_name == "knowledge"
    assert record.version == "1.0"
    assert record.timestamp == "2026-01-01T00:00:00+00:00"
    assert record.payload == {"value": 42}
    assert record.metadata == {"source": "test"}


def test_storage_record_rejects_empty_identifier() -> None:
    with pytest.raises(ValueError):
        StorageRecord.create(
            "",
            "test",
            "1",
            None,
        )


def test_storage_record_rejects_empty_type() -> None:
    with pytest.raises(ValueError):
        StorageRecord.create(
            "id",
            "",
            "1",
            None,
        )


def test_storage_record_rejects_empty_version() -> None:
    with pytest.raises(ValueError):
        StorageRecord.create(
            "id",
            "test",
            "",
            None,
        )


def test_storage_record_with_payload_returns_new_record() -> None:
    record = StorageRecord.create(
        "id",
        "test",
        "1",
        {"value": 1},
        timestamp="2026-01-01T00:00:00+00:00",
    )

    updated = record.with_payload(
        {"value": 2},
        timestamp="2026-01-02T00:00:00+00:00",
    )

    assert record.payload == {"value": 1}
    assert updated.payload == {"value": 2}
    assert updated.identifier == record.identifier
    assert updated.timestamp != record.timestamp


def test_storage_query_matches_identifier() -> None:
    record = StorageRecord.create(
        "id-1",
        "test",
        "1",
        None,
    )

    assert StorageQuery(identifier="id-1").matches(record)
    assert not StorageQuery(identifier="id-2").matches(record)


def test_storage_query_matches_type() -> None:
    record = StorageRecord.create(
        "id",
        "knowledge",
        "1",
        None,
    )

    assert StorageQuery(type_name="knowledge").matches(record)
    assert not StorageQuery(type_name="memory").matches(record)


def test_storage_query_matches_version() -> None:
    record = StorageRecord.create(
        "id",
        "test",
        "2",
        None,
    )

    assert StorageQuery(version="2").matches(record)
    assert not StorageQuery(version="1").matches(record)


def test_storage_query_matches_metadata() -> None:
    record = StorageRecord.create(
        "id",
        "test",
        "1",
        None,
        metadata={"source": "core", "scope": "global"},
    )

    assert StorageQuery(
        metadata={"source": "core"},
    ).matches(record)

    assert StorageQuery(
        metadata={"source": "core", "scope": "global"},
    ).matches(record)

    assert not StorageQuery(
        metadata={"source": "external"},
    ).matches(record)


def test_storage_query_combines_filters() -> None:
    record = StorageRecord.create(
        "id-1",
        "knowledge",
        "1",
        None,
        metadata={"source": "memory"},
    )

    query = StorageQuery(
        identifier="id-1",
        type_name="knowledge",
        version="1",
        metadata={"source": "memory"},
    )

    assert query.matches(record)


def test_storage_query_rejects_negative_limit() -> None:
    with pytest.raises(ValueError):
        StorageQuery(limit=-1)


def test_storage_result_creation() -> None:
    record = StorageRecord.create(
        "id",
        "test",
        "1",
        None,
    )

    result = StorageResult(
        records=(record,),
        total=1,
    )

    assert result.records == (record,)
    assert result.total == 1
    assert result.count == 1
    assert not result.empty


def test_storage_result_empty() -> None:
    result = StorageResult(
        records=(),
        total=0,
    )

    assert result.empty
    assert result.count == 0


def test_storage_result_rejects_invalid_total() -> None:
    record = StorageRecord.create(
        "id",
        "test",
        "1",
        None,
    )

    with pytest.raises(ValueError):
        StorageResult(
            records=(record,),
            total=0,
        )
