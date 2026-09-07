"""
SH-3 Complete Edition v1.0
Foundation Layer
Utilities Subsystem
object.py
"""

from __future__ import annotations

from typing import (
    Any,
    Protocol,
    Self,
    get_type_hints,
    runtime_checkable,
)

from .common import ensure_dict
from .hash import stable_id
from .json import dumps, loads
from .json import normalize as json_normalize

__all__ = [
    "SerializableObject",
    "from_dict",
    "from_json",
    "to_dict",
    "to_json",
]

JSONDict = dict[str, Any]


@runtime_checkable
class SerializableObject(Protocol):
    def to_dict(self) -> JSONDict:
        ...

    @classmethod
    def from_dict(cls, data: JSONDict) -> Self:
        ...


class SH3Object:
    """Lightweight base DTO object for SH-3 system."""

    def to_dict(self) -> dict[str, Any]:
        return ensure_dict(self.__dict__)

    def to_json(self) -> str:
        return dumps(self.to_dict(), ensure_ascii=False)

    def to_hash(self) -> str:
        return stable_id(self.to_dict())

    def clone(self) -> Self:
        return from_dict(self.__class__, self.to_dict())

    @classmethod
    def from_dict[T](cls: type[T], data: dict[Any, Any]) -> T:
        obj = cls.__new__(cls)
        for k, v in data.items():
            setattr(obj, k, v)
        return obj

    @classmethod
    def from_json[T](cls: type[T], data: str) -> T:
        value = loads(data)
        if not isinstance(value, dict):
            raise TypeError("Input must decode to dict")
        return from_dict(cls, value)


def to_dict(obj: Any) -> dict[Any, Any]:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        result = obj.to_dict()
        if isinstance(result, dict):
            return result
    if hasattr(obj, "__dict__"):
        result = obj.__dict__
        if isinstance(result, dict):
            return dict(result)
    raise TypeError("Object is not convertible to dict")


def from_dict[T](cls: type[T], data: dict[Any, Any]) -> T:
    if not isinstance(data, dict):
        raise TypeError("Input must be dict")

    obj = cls.__new__(cls)
    for k, v in data.items():
        setattr(obj, k, v)
    return obj


def to_json(obj: Any) -> str:
    return dumps(json_normalize(to_dict(obj)), ensure_ascii=False)


def from_json[T](cls: type[T], data: str) -> T:
    value = loads(data)
    if not isinstance(value, dict):
        raise TypeError("Input must decode to dict")
    return from_dict(cls, value)


def schema_of(obj: Any) -> dict[str, Any]:
    hints = get_type_hints(obj.__class__) if hasattr(obj, "__class__") else {}
    return {k: str(v) for k, v in hints.items()}


def has_attr(obj: Any, name: str) -> bool:
    return hasattr(obj, name)


def get_attr(obj: Any, name: str, default: Any = None) -> Any:
    return getattr(obj, name, default)


def set_attr(obj: Any, name: str, value: Any) -> Any:
    setattr(obj, name, value)
    return obj


def object_id(obj: Any) -> str:
    return stable_id(to_dict(obj))


def fingerprint(obj: Any) -> str:
    return stable_id(json_normalize(to_dict(obj)))
