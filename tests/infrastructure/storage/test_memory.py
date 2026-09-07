from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from infrastructure.storage.memory import (
    MemoryStorage,
    MemoryStorageTransaction,
)
from infrastructure.storage.model import StorageQuery, StorageRecord
from infrastructure.storage.protocol import (
    StorageConflictError,
    StorageNotFoundError,
    StorageProtocol,
)
from infrastructure.storage.transaction import (
    StorageTransaction,
    TransactionClosedError,
    TransactionConflictError,
)


def record(
    identifier: str = "record-1",
    *,
    type_name: str = "test",
    version: str = "1",
    payload: object = None,
    metadata: dict[str, object] | None = None,
) -> StorageRecord:
    return StorageRecord.create(
        identifier=identifier,
        type_name=type_name,
        version=version,
        payload=payload if payload is not None else {"value": identifier},
        metadata=metadata,
        timestamp="2026-01-01T00:00:00+00:00",
    )


def test_protocol_conformance() -> None:
    storage = MemoryStorage()
    assert isinstance(storage, StorageProtocol)


def test_transaction_protocol_conformance() -> None:
    storage = MemoryStorage()
    transaction = storage.transaction()
    assert isinstance(transaction, StorageTransaction)
    assert isinstance(transaction, MemoryStorageTransaction)
    transaction.rollback()


def test_initial_state() -> None:
    storage = MemoryStorage()
    assert storage.empty()
    assert storage.size() == 0
    assert storage.records() == ()
    assert not storage.contains("missing")


def test_create_and_get() -> None:
    storage = MemoryStorage()
    item = record()
    result = storage.create(item)

    assert result is item
    assert storage.get(item.identifier) is item
    assert storage.size() == 1
    assert not storage.empty()


def test_create_duplicate_raises_conflict() -> None:
    storage = MemoryStorage()
    item = record()

    storage.create(item)

    with pytest.raises(StorageConflictError):
        storage.create(item)


def test_get_missing_raises_not_found() -> None:
    storage = MemoryStorage()

    with pytest.raises(StorageNotFoundError):
        storage.get("missing")


def test_update_replaces_existing_record() -> None:
    storage = MemoryStorage()
    original = record(payload={"value": 1})
    updated = record(payload={"value": 2})

    storage.create(original)

    assert storage.update(updated) is updated
    assert storage.get(original.identifier) is updated
    assert storage.size() == 1


def test_update_missing_raises_not_found() -> None:
    storage = MemoryStorage()

    with pytest.raises(StorageNotFoundError):
        storage.update(record())


def test_delete_returns_removed_record() -> None:
    storage = MemoryStorage()
    item = record()

    storage.create(item)

    assert storage.delete(item.identifier) is item
    assert storage.empty()

    with pytest.raises(StorageNotFoundError):
        storage.get(item.identifier)


def test_delete_missing_raises_not_found() -> None:
    storage = MemoryStorage()

    with pytest.raises(StorageNotFoundError):
        storage.delete("missing")


def test_query_returns_matching_records() -> None:
    storage = MemoryStorage()

    first = record("a", type_name="alpha")
    second = record("b", type_name="beta")
    third = record("c", type_name="alpha")

    storage.create(second)
    storage.create(third)
    storage.create(first)

    result = storage.query(
        StorageQuery(type_name="alpha"),
    )

    assert result.total == 2
    assert result.count == 2
    assert [item.identifier for item in result.records] == ["a", "c"]


def test_query_identifier() -> None:
    storage = MemoryStorage()
    storage.create(record("a"))
    storage.create(record("b"))

    result = storage.query(
        StorageQuery(identifier="b"),
    )

    assert result.total == 1
    assert result.records[0].identifier == "b"


def test_query_version() -> None:
    storage = MemoryStorage()
    storage.create(record("a", version="1"))
    storage.create(record("b", version="2"))

    result = storage.query(
        StorageQuery(version="2"),
    )

    assert [item.identifier for item in result.records] == ["b"]


def test_query_metadata() -> None:
    storage = MemoryStorage()
    storage.create(
        record(
            "a",
            metadata={"role": "worker", "zone": "a"},
        )
    )
    storage.create(
        record(
            "b",
            metadata={"role": "worker", "zone": "b"},
        )
    )

    result = storage.query(
        StorageQuery(
            metadata={"role": "worker", "zone": "b"},
        ),
    )

    assert result.total == 1
    assert result.records[0].identifier == "b"


def test_query_limit() -> None:
    storage = MemoryStorage()

    for identifier in ("a", "b", "c"):
        storage.create(record(identifier))

    result = storage.query(StorageQuery(limit=2))

    assert result.total == 3
    assert result.count == 2
    assert [item.identifier for item in result.records] == ["a", "b"]


def test_query_zero_limit() -> None:
    storage = MemoryStorage()
    storage.create(record("a"))

    result = storage.query(StorageQuery(limit=0))

    assert result.total == 1
    assert result.records == ()
    assert result.count == 0
    assert result.empty


def test_query_is_deterministically_sorted() -> None:
    storage = MemoryStorage()

    for identifier in ("z", "c", "a", "m", "b"):
        storage.create(record(identifier))

    result = storage.query(StorageQuery())

    assert [item.identifier for item in result.records] == [
        "a",
        "b",
        "c",
        "m",
        "z",
    ]


def test_records_are_deterministically_sorted() -> None:
    storage = MemoryStorage()

    for identifier in ("z", "a", "m"):
        storage.create(record(identifier))

    assert [item.identifier for item in storage.records()] == ["a", "m", "z"]


def test_contains() -> None:
    storage = MemoryStorage()
    storage.create(record("a"))

    assert storage.contains("a")
    assert not storage.contains("b")


def test_clear() -> None:
    storage = MemoryStorage()
    storage.create(record("a"))
    storage.create(record("b"))

    storage.clear()

    assert storage.empty()
    assert storage.size() == 0
    assert storage.records() == ()


def test_clear_empty_storage_is_noop() -> None:
    storage = MemoryStorage()
    snapshot = storage.snapshot()

    storage.clear()

    assert storage.snapshot() == snapshot


def test_snapshot_tracks_mutations() -> None:
    storage = MemoryStorage()

    initial = storage.snapshot()
    assert initial.size == 0
    assert initial.created == 0
    assert initial.updated == 0
    assert initial.deleted == 0
    assert initial.version == 0

    storage.create(record("a"))
    storage.update(record("a", payload={"updated": True}))
    storage.delete("a")

    snapshot = storage.snapshot()

    assert snapshot.size == 0
    assert snapshot.created == 1
    assert snapshot.updated == 1
    assert snapshot.deleted == 1
    assert snapshot.version == 3


def test_metrics_alias_snapshot() -> None:
    storage = MemoryStorage()
    storage.create(record("a"))

    assert storage.metrics() == storage.snapshot()


def test_query_metrics_increment() -> None:
    storage = MemoryStorage()

    storage.query(StorageQuery())
    storage.query(StorageQuery())

    assert storage.snapshot().queried == 2


def test_create_requires_storage_record() -> None:
    storage = MemoryStorage()

    with pytest.raises(TypeError):
        storage.create(object())  # type: ignore[arg-type]


def test_update_requires_storage_record() -> None:
    storage = MemoryStorage()

    with pytest.raises(TypeError):
        storage.update(object())  # type: ignore[arg-type]


def test_get_requires_non_empty_identifier() -> None:
    storage = MemoryStorage()

    with pytest.raises(ValueError):
        storage.get("")


def test_delete_requires_non_empty_identifier() -> None:
    storage = MemoryStorage()

    with pytest.raises(ValueError):
        storage.delete("")


def test_query_requires_storage_query() -> None:
    storage = MemoryStorage()

    with pytest.raises(TypeError):
        storage.query(object())  # type: ignore[arg-type]


def test_transaction_initial_state() -> None:
    storage = MemoryStorage()
    transaction = storage.transaction()

    assert transaction.active
    assert storage.snapshot().transactions == 1

    transaction.rollback()

    assert not transaction.active
    assert storage.snapshot().rolled_back == 1


def test_transaction_create_is_staged() -> None:
    storage = MemoryStorage()
    transaction = storage.transaction()

    item = record()

    transaction.create(item)

    assert transaction.get(item.identifier) is item
    assert storage.empty()

    transaction.commit()

    assert storage.get(item.identifier) is item
    assert storage.size() == 1


def test_transaction_update_is_staged() -> None:
    storage = MemoryStorage()
    original = record(payload={"value": 1})
    updated = record(payload={"value": 2})

    storage.create(original)

    transaction = storage.transaction()
    transaction.update(updated)

    assert transaction.get("record-1") is updated
    assert storage.get("record-1") is original

    transaction.commit()

    assert storage.get("record-1") is updated


def test_transaction_delete_is_staged() -> None:
    storage = MemoryStorage()
    item = record()

    storage.create(item)

    transaction = storage.transaction()

    assert transaction.delete(item.identifier) is item
    assert transaction.active
    assert storage.contains(item.identifier)

    transaction.commit()

    assert not storage.contains(item.identifier)


def test_transaction_query_uses_transaction_view() -> None:
    storage = MemoryStorage()
    storage.create(record("a"))

    transaction = storage.transaction()
    transaction.create(record("b"))

    result = transaction.query(StorageQuery())

    assert [item.identifier for item in result.records] == ["a", "b"]
    assert storage.size() == 1

    transaction.rollback()


def test_transaction_duplicate_create_raises_conflict() -> None:
    storage = MemoryStorage()
    storage.create(record("a"))

    transaction = storage.transaction()

    with pytest.raises(StorageConflictError):
        transaction.create(record("a"))

    transaction.rollback()


def test_transaction_missing_update_raises_not_found() -> None:
    storage = MemoryStorage()
    transaction = storage.transaction()

    with pytest.raises(StorageNotFoundError):
        transaction.update(record("missing"))

    transaction.rollback()


def test_transaction_missing_delete_raises_not_found() -> None:
    storage = MemoryStorage()
    transaction = storage.transaction()

    with pytest.raises(StorageNotFoundError):
        transaction.delete("missing")

    transaction.rollback()


def test_transaction_missing_get_raises_not_found() -> None:
    storage = MemoryStorage()
    transaction = storage.transaction()

    with pytest.raises(StorageNotFoundError):
        transaction.get("missing")

    transaction.rollback()


def test_transaction_commit_is_atomic() -> None:
    storage = MemoryStorage()

    transaction = storage.transaction()
    transaction.create(record("a"))
    transaction.create(record("b"))

    assert storage.empty()

    transaction.commit()

    assert storage.size() == 2
    assert storage.contains("a")
    assert storage.contains("b")


def test_transaction_rollback_discards_changes() -> None:
    storage = MemoryStorage()

    transaction = storage.transaction()
    transaction.create(record("a"))
    transaction.create(record("b"))

    transaction.rollback()

    assert storage.empty()


def test_transaction_commit_closes_transaction() -> None:
    storage = MemoryStorage()
    transaction = storage.transaction()

    transaction.commit()

    assert not transaction.active

    with pytest.raises(TransactionClosedError):
        transaction.get("missing")


def test_transaction_rollback_closes_transaction() -> None:
    storage = MemoryStorage()
    transaction = storage.transaction()

    transaction.rollback()

    assert not transaction.active

    with pytest.raises(TransactionClosedError):
        transaction.get("missing")


def test_transaction_double_commit_raises() -> None:
    storage = MemoryStorage()
    transaction = storage.transaction()

    transaction.commit()

    with pytest.raises(TransactionClosedError):
        transaction.commit()


def test_transaction_double_rollback_raises() -> None:
    storage = MemoryStorage()
    transaction = storage.transaction()

    transaction.rollback()

    with pytest.raises(TransactionClosedError):
        transaction.rollback()


def test_transaction_conflict_detection() -> None:
    storage = MemoryStorage()
    storage.create(record("a"))

    transaction = storage.transaction()
    transaction.update(record("a", payload={"transaction": True}))

    storage.update(record("a", payload={"external": True}))

    with pytest.raises(TransactionConflictError):
        transaction.commit()

    assert storage.get("a").payload == {"external": True}
    assert not transaction.active


def test_transaction_commit_updates_metrics() -> None:
    storage = MemoryStorage()
    transaction = storage.transaction()

    transaction.create(record("a"))
    transaction.commit()

    snapshot = storage.snapshot()

    assert snapshot.transactions == 1
    assert snapshot.committed == 1


def test_transaction_rollback_updates_metrics() -> None:
    storage = MemoryStorage()
    transaction = storage.transaction()

    transaction.create(record("a"))
    transaction.rollback()

    snapshot = storage.snapshot()

    assert snapshot.transactions == 1
    assert snapshot.rolled_back == 1
    assert snapshot.committed == 0


def test_transaction_begin_alias() -> None:
    storage = MemoryStorage()

    transaction = storage.begin()

    assert isinstance(transaction, MemoryStorageTransaction)
    assert transaction.active

    transaction.rollback()


def test_transaction_snapshot_isolation_for_reads() -> None:
    storage = MemoryStorage()
    storage.create(record("a", payload={"value": 1}))

    transaction = storage.transaction()

    storage.update(record("a", payload={"value": 2}))

    assert transaction.get("a").payload == {"value": 1}

    transaction.rollback()


def test_transaction_commit_detects_external_create() -> None:
    storage = MemoryStorage()

    transaction = storage.transaction()
    transaction.create(record("a"))

    storage.create(record("b"))

    with pytest.raises(TransactionConflictError):
        transaction.commit()

    assert not storage.contains("a")
    assert storage.contains("b")


def test_concurrent_create_operations_are_safe() -> None:
    storage = MemoryStorage()

    def create_item(index: int) -> StorageRecord:
        item = record(f"record-{index:03d}")
        storage.create(item)
        return item

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = tuple(executor.map(create_item, range(50)))

    assert len(results) == 50
    assert storage.size() == 50
    assert storage.snapshot().created == 50


def test_concurrent_reads_are_safe() -> None:
    storage = MemoryStorage()

    for index in range(50):
        storage.create(record(f"record-{index:03d}"))

    def read_item(index: int) -> StorageRecord:
        return storage.get(f"record-{index:03d}")

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = tuple(executor.map(read_item, range(50)))

    assert len(results) == 50
    assert {item.identifier for item in results} == {f"record-{index:03d}" for index in range(50)}


def test_concurrent_queries_are_safe() -> None:
    storage = MemoryStorage()

    for index in range(50):
        storage.create(record(f"record-{index:03d}"))

    def query(_: int) -> tuple[str, ...]:
        result = storage.query(StorageQuery())
        return tuple(item.identifier for item in result.records)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = tuple(executor.map(query, range(50)))

    expected = tuple(f"record-{index:03d}" for index in range(50))

    assert all(result == expected for result in results)
