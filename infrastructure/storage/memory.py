"""
SH-3 Complete Edition v2.0
Infrastructure Layer
Storage Subsystem

Deterministic thread-safe in-memory storage backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Final

from .model import StorageQuery, StorageRecord, StorageResult
from .protocol import (
    StorageConflictError,
    StorageNotFoundError,
    StorageProtocol,
)
from .transaction import (
    StorageTransaction,
    TransactionClosedError,
    TransactionConflictError,
)

__all__ = [
    "MemoryStorage",
    "MemoryStorageSnapshot",
    "MemoryStorageTransaction",
]


@dataclass(frozen=True, slots=True)
class MemoryStorageSnapshot:
    size: int
    created: int
    updated: int
    deleted: int
    queried: int
    transactions: int
    committed: int
    rolled_back: int
    version: int


class MemoryStorage:
    """Thread-safe deterministic in-memory storage backend."""

    _EMPTY_VERSION: Final[int] = 0

    def __init__(self) -> None:
        self._records: dict[str, StorageRecord] = {}
        self._lock = RLock()
        self._version = self._EMPTY_VERSION
        self._created = 0
        self._updated = 0
        self._deleted = 0
        self._queried = 0
        self._transactions = 0
        self._committed = 0
        self._rolled_back = 0

    def create(self, record: StorageRecord) -> StorageRecord:
        self._validate_record(record)

        with self._lock:
            if record.identifier in self._records:
                raise StorageConflictError(f"record already exists: {record.identifier}")
            self._records[record.identifier] = record
            self._version += 1
            self._created += 1
            return record

    def get(self, identifier: str) -> StorageRecord:
        self._validate_identifier(identifier)

        with self._lock:
            try:
                return self._records[identifier]
            except KeyError as exc:
                raise StorageNotFoundError(f"record not found: {identifier}") from exc

    def update(self, record: StorageRecord) -> StorageRecord:
        self._validate_record(record)

        with self._lock:
            if record.identifier not in self._records:
                raise StorageNotFoundError(f"record not found: {record.identifier}")
            self._records[record.identifier] = record
            self._version += 1
            self._updated += 1
            return record

    def delete(self, identifier: str) -> StorageRecord:
        self._validate_identifier(identifier)

        with self._lock:
            try:
                record = self._records.pop(identifier)
            except KeyError as exc:
                raise StorageNotFoundError(f"record not found: {identifier}") from exc

            self._version += 1
            self._deleted += 1
            return record

    def query(self, query: StorageQuery) -> StorageResult:
        if not isinstance(query, StorageQuery):
            raise TypeError("query must be StorageQuery")

        with self._lock:
            records = tuple(
                record
                for record in sorted(
                    self._records.values(),
                    key=lambda item: item.identifier,
                )
                if query.matches(record)
            )
            self._queried += 1

        total = len(records)

        if query.limit is not None:
            records = records[: query.limit]

        return StorageResult(
            records=records,
            total=total,
        )

    def clear(self) -> None:
        with self._lock:
            if not self._records:
                return
            self._records.clear()
            self._version += 1

    def size(self) -> int:
        with self._lock:
            return len(self._records)

    def empty(self) -> bool:
        with self._lock:
            return not self._records

    def transaction(self) -> MemoryStorageTransaction:
        with self._lock:
            snapshot = dict(self._records)
            version = self._version
            self._transactions += 1

        return MemoryStorageTransaction(
            storage=self,
            records=snapshot,
            base_version=version,
        )

    def begin(self) -> MemoryStorageTransaction:
        return self.transaction()

    def snapshot(self) -> MemoryStorageSnapshot:
        with self._lock:
            return MemoryStorageSnapshot(
                size=len(self._records),
                created=self._created,
                updated=self._updated,
                deleted=self._deleted,
                queried=self._queried,
                transactions=self._transactions,
                committed=self._committed,
                rolled_back=self._rolled_back,
                version=self._version,
            )

    def metrics(self) -> MemoryStorageSnapshot:
        return self.snapshot()

    def contains(self, identifier: str) -> bool:
        self._validate_identifier(identifier)

        with self._lock:
            return identifier in self._records

    def records(self) -> tuple[StorageRecord, ...]:
        with self._lock:
            return tuple(
                sorted(
                    self._records.values(),
                    key=lambda item: item.identifier,
                )
            )

    def _commit(
        self,
        records: dict[str, StorageRecord],
        base_version: int,
    ) -> None:
        with self._lock:
            if self._version != base_version:
                raise TransactionConflictError("storage changed during transaction")

            self._records = dict(records)
            self._version += 1
            self._committed += 1

    def _rollback(self) -> None:
        with self._lock:
            self._rolled_back += 1

    @staticmethod
    def _validate_identifier(identifier: str) -> None:
        if not isinstance(identifier, str):
            raise TypeError("identifier must be str")
        if not identifier:
            raise ValueError("identifier must not be empty")

    @staticmethod
    def _validate_record(record: StorageRecord) -> None:
        if not isinstance(record, StorageRecord):
            raise TypeError("record must be StorageRecord")


class MemoryStorageTransaction:
    """Atomic snapshot transaction for MemoryStorage."""

    def __init__(
        self,
        *,
        storage: MemoryStorage,
        records: dict[str, StorageRecord],
        base_version: int,
    ) -> None:
        self._storage = storage
        self._records = records
        self._base_version = base_version
        self._active = True
        self._lock = RLock()

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active

    def create(self, record: StorageRecord) -> StorageRecord:
        self._ensure_active()
        self._validate_record(record)

        with self._lock:
            if record.identifier in self._records:
                raise StorageConflictError(f"record already exists: {record.identifier}")
            self._records[record.identifier] = record
            return record

    def get(self, identifier: str) -> StorageRecord:
        self._ensure_active()
        self._validate_identifier(identifier)

        with self._lock:
            try:
                return self._records[identifier]
            except KeyError as exc:
                raise StorageNotFoundError(f"record not found: {identifier}") from exc

    def update(self, record: StorageRecord) -> StorageRecord:
        self._ensure_active()
        self._validate_record(record)

        with self._lock:
            if record.identifier not in self._records:
                raise StorageNotFoundError(f"record not found: {record.identifier}")
            self._records[record.identifier] = record
            return record

    def delete(self, identifier: str) -> StorageRecord:
        self._ensure_active()
        self._validate_identifier(identifier)

        with self._lock:
            try:
                return self._records.pop(identifier)
            except KeyError as exc:
                raise StorageNotFoundError(f"record not found: {identifier}") from exc

    def query(self, query: StorageQuery) -> StorageResult:
        self._ensure_active()

        if not isinstance(query, StorageQuery):
            raise TypeError("query must be StorageQuery")

        with self._lock:
            records = tuple(
                record
                for record in sorted(
                    self._records.values(),
                    key=lambda item: item.identifier,
                )
                if query.matches(record)
            )

        total = len(records)

        if query.limit is not None:
            records = records[: query.limit]

        return StorageResult(
            records=records,
            total=total,
        )

    def commit(self) -> None:
        self._ensure_active()

        with self._lock:
            records = dict(self._records)
            base_version = self._base_version

        try:
            self._storage._commit(records, base_version)
        except TransactionConflictError:
            with self._lock:
                self._active = False
            raise

        with self._lock:
            self._active = False

    def rollback(self) -> None:
        self._ensure_active()

        with self._lock:
            self._records.clear()
            self._active = False

        self._storage._rollback()

    def _ensure_active(self) -> None:
        with self._lock:
            if not self._active:
                raise TransactionClosedError("transaction is closed")

    @staticmethod
    def _validate_identifier(identifier: str) -> None:
        if not isinstance(identifier, str):
            raise TypeError("identifier must be str")
        if not identifier:
            raise ValueError("identifier must not be empty")

    @staticmethod
    def _validate_record(record: StorageRecord) -> None:
        if not isinstance(record, StorageRecord):
            raise TypeError("record must be StorageRecord")


assert isinstance(MemoryStorage(), StorageProtocol)
assert isinstance(
    MemoryStorage().transaction(),
    StorageTransaction,
)
