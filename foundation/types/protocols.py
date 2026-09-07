"""
SH-3 Complete Edition v1.0
Foundation Layer
Types Subsystem
protocols.py
Kernel Protocol Definitions.
"""

from __future__ import annotations

from typing import Any, Protocol, Self, runtime_checkable

__all__ = [
    "Cloneable",
    "HashableObject",
    "Identifiable",
    "MetadataContainer",
    "NamedObject",
    "Serializable",
    "Validatable",
]


@runtime_checkable
class Serializable(Protocol):
    def to_dict(self) -> dict[str, Any]:
        ...

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        ...


@runtime_checkable
class Validatable(Protocol):
    def validate(self) -> None:
        ...


@runtime_checkable
class Cloneable(Protocol):
    def copy(self) -> Self:
        ...


@runtime_checkable
class HashableObject(Protocol):
    def __hash__(self) -> int:
        ...


@runtime_checkable
class NamedObject(Protocol):
    @property
    def name(self) -> str:
        ...


@runtime_checkable
class Identifiable(Protocol):
    @property
    def id(self) -> str:
        ...


@runtime_checkable
class MetadataContainer(Protocol):
    @property
    def metadata(self) -> dict[str, Any]:
        ...
