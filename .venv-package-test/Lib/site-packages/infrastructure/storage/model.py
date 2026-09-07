"""
SH-3 Complete Edition v2.0
Infrastructure Layer
Storage Subsystem

Immutable storage models.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

__all__ = [
    "StorageQuery",
    "StorageRecord",
    "StorageResult",
]


def _validate_identifier(value: str, name: str = "identifier") -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value:
        raise ValueError(f"{name} must not be empty")


def _validate_mapping(
    value: Mapping[str, Any],
    name: str,
) -> None:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")


@dataclass(frozen=True, slots=True)
class StorageRecord:
    identifier: str
    type_name: str
    version: str
    timestamp: str
    payload: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_identifier(self.identifier)
        _validate_identifier(self.type_name, "type_name")
        _validate_identifier(self.version, "version")
        _validate_identifier(self.timestamp, "timestamp")
        _validate_mapping(self.metadata, "metadata")

    @classmethod
    def create(
        cls,
        identifier: str,
        type_name: str,
        version: str,
        payload: Any,
        *,
        metadata: Mapping[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> StorageRecord:
        return cls(
            identifier=identifier,
            type_name=type_name,
            version=version,
            timestamp=(timestamp if timestamp is not None else datetime.now(UTC).isoformat()),
            payload=payload,
            metadata=dict(metadata or {}),
        )

    def with_payload(
        self,
        payload: Any,
        *,
        metadata: Mapping[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> StorageRecord:
        return StorageRecord(
            identifier=self.identifier,
            type_name=self.type_name,
            version=self.version,
            timestamp=(timestamp if timestamp is not None else datetime.now(UTC).isoformat()),
            payload=payload,
            metadata=(dict(self.metadata) if metadata is None else dict(metadata)),
        )


@dataclass(frozen=True, slots=True)
class StorageQuery:
    identifier: str | None = None
    type_name: str | None = None
    version: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    limit: int | None = None

    def __post_init__(self) -> None:
        if self.identifier is not None:
            _validate_identifier(self.identifier)

        if self.type_name is not None:
            _validate_identifier(self.type_name, "type_name")

        if self.version is not None:
            _validate_identifier(self.version, "version")

        _validate_mapping(self.metadata, "metadata")

        if self.limit is not None:
            if not isinstance(self.limit, int):
                raise TypeError("limit must be int or None")
            if self.limit < 0:
                raise ValueError("limit must be >= 0")

    def matches(self, record: StorageRecord) -> bool:
        if self.identifier is not None and record.identifier != self.identifier:
            return False

        if self.type_name is not None and record.type_name != self.type_name:
            return False

        if self.version is not None and record.version != self.version:
            return False

        return all(
            record.metadata.get(key) == value
            for key, value in self.metadata.items()
        )


@dataclass(frozen=True, slots=True)
class StorageResult:
    records: tuple[StorageRecord, ...]
    total: int

    def __post_init__(self) -> None:
        if not isinstance(self.records, tuple):
            raise TypeError("records must be tuple")

        if self.total < 0:
            raise ValueError("total must be >= 0")

        if self.total < len(self.records):
            raise ValueError("total must be >= number of returned records")

    @property
    def empty(self) -> bool:
        return not self.records

    @property
    def count(self) -> int:
        return len(self.records)
