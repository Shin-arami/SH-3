"""
SH-3 Complete Edition v2.0
Infrastructure Layer
Storage Subsystem

Transaction contracts.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .model import StorageQuery, StorageRecord, StorageResult

__all__ = [
    "StorageTransaction",
    "TransactionClosedError",
    "TransactionConflictError",
    "TransactionError",
]


class TransactionError(Exception):
    """Base exception for storage transaction failures."""


class TransactionClosedError(TransactionError):
    """Raised when an operation is attempted on a closed transaction."""


class TransactionConflictError(TransactionError):
    """Raised when a transaction cannot be committed safely."""


@runtime_checkable
class StorageTransaction(Protocol):
    """Atomic storage transaction contract."""

    @property
    def active(self) -> bool:
        """Return whether the transaction is active."""

    def create(
        self,
        record: StorageRecord,
    ) -> StorageRecord:
        """Stage a new record."""

    def get(
        self,
        identifier: str,
    ) -> StorageRecord:
        """Read a record from the transaction view."""

    def update(
        self,
        record: StorageRecord,
    ) -> StorageRecord:
        """Stage an existing record replacement."""

    def delete(
        self,
        identifier: str,
    ) -> StorageRecord:
        """Stage deletion and return the record."""

    def query(
        self,
        query: StorageQuery,
    ) -> StorageResult:
        """Query the transaction view."""

    def commit(self) -> None:
        """Atomically commit staged changes."""

    def rollback(self) -> None:
        """Discard all staged changes."""
