"""
SH-3 Complete Edition v2.0
Infrastructure Layer
Events Subsystem

registry.py

Canonical event schema registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Final

from foundation.Enums.category import Category

__all__ = [
    "EventSchema",
    "EventSchemaRegistry",
    "SchemaKey",
]


@dataclass(frozen=True, slots=True)
class SchemaKey:
    identifier: str
    version: str

    def __post_init__(self) -> None:
        if not self.identifier:
            raise ValueError("schema identifier must not be empty")
        if not self.version:
            raise ValueError("schema version must not be empty")


@dataclass(frozen=True, slots=True)
class EventSchema:
    identifier: str
    version: str
    owner: str
    category: Category
    specification: str

    def __post_init__(self) -> None:
        if not self.identifier:
            raise ValueError("schema identifier must not be empty")
        if not self.version:
            raise ValueError("schema version must not be empty")
        if not self.owner:
            raise ValueError("schema owner must not be empty")
        if not isinstance(self.category, Category):
            raise TypeError("category must be Category")
        if not self.specification:
            raise ValueError("specification reference must not be empty")

    @property
    def key(self) -> SchemaKey:
        return SchemaKey(
            identifier=self.identifier,
            version=self.version,
        )


class EventSchemaRegistry:
    """Thread-safe registry for production event schemas."""

    _DEFAULT_VERSION: Final[str] = "1.0.0"

    def __init__(self) -> None:
        self._schemas: dict[SchemaKey, EventSchema] = {}
        self._lock = RLock()

    def register(
        self,
        schema: EventSchema,
        *,
        replace: bool = False,
    ) -> None:
        if not isinstance(schema, EventSchema):
            raise TypeError("schema must be EventSchema")

        key = schema.key

        with self._lock:
            if key in self._schemas and not replace:
                raise ValueError(f"schema already registered: {schema.identifier}@{schema.version}")
            self._schemas[key] = schema

    def unregister(
        self,
        identifier: str,
        version: str,
    ) -> EventSchema:
        key = SchemaKey(identifier, version)

        with self._lock:
            try:
                return self._schemas.pop(key)
            except KeyError as exc:
                raise KeyError(f"schema not registered: {identifier}@{version}") from exc

    def get(
        self,
        identifier: str,
        version: str | None = None,
    ) -> EventSchema:
        with self._lock:
            if version is not None:
                key = SchemaKey(identifier, version)
                try:
                    return self._schemas[key]
                except KeyError as exc:
                    raise KeyError(f"schema not registered: {identifier}@{version}") from exc

            matches = [
                schema for schema in self._schemas.values() if schema.identifier == identifier
            ]

        if not matches:
            raise KeyError(f"schema not registered: {identifier}")

        return max(
            matches,
            key=lambda schema: self._version_key(schema.version),
        )

    def contains(
        self,
        identifier: str,
        version: str | None = None,
    ) -> bool:
        with self._lock:
            if version is not None:
                return SchemaKey(identifier, version) in self._schemas

            return any(schema.identifier == identifier for schema in self._schemas.values())

    def list(
        self,
        identifier: str | None = None,
    ) -> tuple[EventSchema, ...]:
        with self._lock:
            schemas = tuple(self._schemas.values())

        if identifier is not None:
            schemas = tuple(schema for schema in schemas if schema.identifier == identifier)

        return tuple(
            sorted(
                schemas,
                key=lambda schema: (
                    schema.identifier,
                    self._version_key(schema.version),
                ),
            )
        )

    def clear(self) -> None:
        with self._lock:
            self._schemas.clear()

    def count(self) -> int:
        with self._lock:
            return len(self._schemas)

    def validate_reference(
        self,
        identifier: str,
        version: str,
    ) -> bool:
        return self.contains(identifier, version)

    @staticmethod
    def _version_key(
        version: str,
    ) -> tuple[int, int, int, str]:
        parts = version.split(".", 2)

        numbers: list[int] = []

        for part in parts[:3]:
            try:
                numbers.append(int(part))
            except ValueError:
                numbers.append(0)

        while len(numbers) < 3:
            numbers.append(0)

        suffix = parts[2] if len(parts) == 3 else ""

        return (
            numbers[0],
            numbers[1],
            numbers[2],
            suffix,
        )
