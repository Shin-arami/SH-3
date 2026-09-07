from __future__ import annotations

from typing import Any

from infrastructure.storage import (
    StorageRecord,
    StorageResult,
    StorageTransaction,
    TransactionClosedError,
    TransactionConflictError,
    TransactionError,
)


def test_transaction_error_hierarchy() -> None:
    assert issubclass(TransactionClosedError, TransactionError)
    assert issubclass(TransactionConflictError, TransactionError)


def test_transaction_protocol_is_runtime_checkable() -> None:
    class DummyTransaction:
        def __init__(self) -> None:
            self._active = True

        @property
        def active(self) -> bool:
            return self._active

        def create(self, record: Any) -> Any:
            return record

        def get(self, identifier: Any) -> Any:
            raise KeyError(identifier)

        def update(self, record: Any) -> Any:
            return record

        def delete(self, identifier: Any) -> Any:
            raise KeyError(identifier)

        def query(self, query: Any) -> StorageResult:
            return StorageResult((), 0)

        def commit(self) -> None:
            self._active = False

        def rollback(self) -> None:
            self._active = False

    transaction = DummyTransaction()

    assert isinstance(transaction, StorageTransaction)
    assert transaction.active


def test_transaction_commit_changes_active_state() -> None:
    class DummyTransaction:
        def __init__(self) -> None:
            self._active = True

        @property
        def active(self) -> bool:
            return self._active

        def create(self, record: Any) -> Any:
            return record

        def get(self, identifier: Any) -> Any:
            raise KeyError(identifier)

        def update(self, record: Any) -> Any:
            return record

        def delete(self, identifier: Any) -> Any:
            raise KeyError(identifier)

        def query(self, query: Any) -> StorageResult:
            return StorageResult((), 0)

        def commit(self) -> None:
            self._active = False

        def rollback(self) -> None:
            self._active = False

    transaction = DummyTransaction()

    assert transaction.active

    transaction.commit()

    assert not transaction.active


def test_transaction_rollback_changes_active_state() -> None:
    class DummyTransaction:
        def __init__(self) -> None:
            self._active = True

        @property
        def active(self) -> bool:
            return self._active

        def create(self, record: Any) -> Any:
            return record

        def get(self, identifier: Any) -> Any:
            raise KeyError(identifier)

        def update(self, record: Any) -> Any:
            return record

        def delete(self, identifier: Any) -> Any:
            raise KeyError(identifier)

        def query(self, query: Any) -> StorageResult:
            return StorageResult((), 0)

        def commit(self) -> None:
            self._active = False

        def rollback(self) -> None:
            self._active = False

    transaction = DummyTransaction()

    assert transaction.active

    transaction.rollback()

    assert not transaction.active


def test_storage_record_can_be_staged_by_protocol() -> None:
    class DummyTransaction:
        @property
        def active(self) -> bool:
            return True

        def create(self, record: Any) -> Any:
            return record

        def get(self, identifier: Any) -> Any:
            raise KeyError(identifier)

        def update(self, record: Any) -> Any:
            return record

        def delete(self, identifier: Any) -> Any:
            raise KeyError(identifier)

        def query(self, query: Any) -> StorageResult:
            return StorageResult((), 0)

        def commit(self) -> None:
            return None

        def rollback(self) -> None:
            return None

    record = StorageRecord.create(
        "transaction-record",
        "test",
        "1",
        {"value": 1},
    )

    transaction = DummyTransaction()

    assert transaction.create(record) == record
