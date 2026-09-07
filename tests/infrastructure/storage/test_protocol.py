from __future__ import annotations

from typing import Any

from infrastructure.storage import (
    StorageConflictError,
    StorageError,
    StorageNotFoundError,
    StorageProtocol,
    StorageResult,
)


def test_storage_error_hierarchy() -> None:
    assert issubclass(StorageNotFoundError, StorageError)
    assert issubclass(StorageConflictError, StorageError)


def test_storage_protocol_is_runtime_checkable() -> None:
    class DummyStorage:
        def create(self, record: Any) -> Any:
            return record

        def get(self, identifier: Any) -> Any:
            raise StorageNotFoundError(identifier)

        def update(self, record: Any) -> Any:
            return record

        def delete(self, identifier: Any) -> Any:
            raise StorageNotFoundError(identifier)

        def query(self, query: Any) -> StorageResult:
            return StorageResult((), 0)

        def clear(self) -> None:
            return None

        def size(self) -> int:
            return 0

        def empty(self) -> bool:
            return True

    storage = DummyStorage()

    assert isinstance(storage, StorageProtocol)
