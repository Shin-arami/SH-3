"""
SH-3 Complete Edition v2.0
Foundation Layer
Types Subsystem

aliases.py

Kernel type aliases.
"""

from __future__ import annotations

from collections.abc import (
    Callable,
    Iterable,
    Iterator,
    Mapping,
    MutableMapping,
    MutableSequence,
    MutableSet,
    Sequence,
)
from types import MappingProxyType
from typing import Any, Final, Literal

__all__ = [
    "EMPTY_MAPPING",
    "AnyDict",
    "AnyList",
    "AnyTuple",
    "AttributeMap",
    "Callback",
    "Category",
    "Comparator",
    "ComponentId",
    "Confidence",
    "Duration",
    "Embedding",
    "EntityId",
    "Identifier",
    "JSONArray",
    "JSONObject",
    "JSONPrimitive",
    "JSONValue",
    "MetadataMap",
    "MutableList",
    "MutableObjectMap",
    "MutableSetType",
    "MutableStringMap",
    "NodeId",
    "ObjectMap",
    "PacketId",
    "Predicate",
    "Probability",
    "ReadonlyMapping",
    "ReadonlySequence",
    "Role",
    "Score",
    "SessionId",
    "Status",
    "StringIterable",
    "StringIterator",
    "StringMap",
    "StringSequence",
    "TaskId",
    "Timestamp",
    "TraceId",
    "Weight",
]

type AnyDict = dict[str, Any]
type AnyList = list[Any]
type AnyTuple = tuple[Any, ...]

type JSONPrimitive = str | int | float | bool | None
type JSONArray = list[JSONValue]
type JSONObject = dict[str, JSONValue]
type JSONValue = JSONPrimitive | JSONArray | JSONObject

type ReadonlyMapping = Mapping[str, Any]
type ReadonlySequence = Sequence[Any]

type StringMap = dict[str, str]
type ObjectMap = dict[str, Any]
type AttributeMap = dict[str, Any]
type MetadataMap = dict[str, Any]

type Callback = Callable[..., Any]
type Predicate = Callable[[Any], bool]
type Comparator = Callable[[Any, Any], int]

type Identifier = str
type NodeId = str
type ComponentId = str
type EntityId = str
type PacketId = str
type SessionId = str
type TraceId = str
type TaskId = str

type Timestamp = float
type Duration = float

type Probability = float
type Confidence = float
type Score = float
type Weight = float
type Embedding = list[float]

type Status = Literal[
    "created",
    "ready",
    "running",
    "paused",
    "completed",
    "failed",
    "deleted",
]

type Role = Literal[
    "system",
    "user",
    "assistant",
    "tool",
]

type Category = str

type StringSequence = Sequence[str]
type StringIterable = Iterable[str]
type StringIterator = Iterator[str]

type MutableStringMap = MutableMapping[str, str]
type MutableObjectMap = MutableMapping[str, Any]
type MutableList = MutableSequence[Any]
type MutableSetType = MutableSet[Any]

EMPTY_MAPPING: Final[MappingProxyType[str, Any]] = MappingProxyType({})
