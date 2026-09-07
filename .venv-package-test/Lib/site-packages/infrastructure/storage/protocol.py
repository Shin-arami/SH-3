"""
SH-3 Complete Edition v2.0
Infrastructure Layer
Storage Subsystem

Storage contracts.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .model import StorageQuery, StorageRecord, StorageResult

__all__ = [
    "StorageConflictError",
    "StorageError",
    "StorageNotFoundError",
    "StorageProtocol",
]


class StorageError(Exception):
    """Base exception for storage failures."""


class StorageNotFoundError(StorageError):
    """Raised when a requested record does not exist."""


class StorageConflictError(StorageError):
    """Raised when a storage operation conflicts with existing state."""


@runtime_checkable
class StorageProtocol(Protocol):
    """Canonical replaceable storage contract."""

    def create(
        self,
        record: StorageRecord,
    ) -> StorageRecord:
        """Create a new record."""

    def get(
        self,
        identifier: str,
    ) -> StorageRecord:
        """Retrieve one record by identifier."""

    def update(
        self,
        record: StorageRecord,
    ) -> StorageRecord:
        """Replace an existing record."""

    def delete(
        self,
        identifier: str,
    ) -> StorageRecord:
        """Delete and return one record."""

    def query(
        self,
        query: StorageQuery,
    ) -> StorageResult:
        """Query records."""

    def clear(self) -> None:
        """Remove all records."""

    def size(self) -> int:
        """Return the number of stored records."""

    def empty(self) -> bool:
        """Return whether storage contains no records."""
