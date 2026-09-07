"""
SH-3 Complete Edition v1.0
Foundation Layer
Types Subsystem
collections.py
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Hashable, Iterable, Iterator, Mapping
from types import MappingProxyType
from typing import TypeVar, overload

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")
H = TypeVar("H", bound=Hashable)


type Nested[T] = T | list[Nested[T]] | tuple[Nested[T], ...] | set[Nested[T]] | frozenset[Nested[T]]


__all__ = [
    "FrozenDict",
    "FrozenList",
    "RingBuffer",
    "UniqueList",
    "flatten",
    "group_by",
]


class FrozenDict[K, V](Mapping[K, V]):
    __slots__ = ("__data",)

    def __init__(self, data: Mapping[K, V] | Iterable[tuple[K, V]] = ()) -> None:
        self.__data: dict[K, V] = dict(data)

    def __getitem__(self, key: K) -> V:
        return self.__data[key]

    def __iter__(self) -> Iterator[K]:
        return iter(self.__data)

    def __len__(self) -> int:
        return len(self.__data)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.__data!r})"

    def __hash__(self) -> int:
        return hash(frozenset(self.__data.items()))

    def proxy(self) -> MappingProxyType[K, V]:
        return MappingProxyType(self.__data)

    def copy(self) -> FrozenDict[K, V]:
        return FrozenDict(self.__data)


class FrozenList[T](tuple[T, ...]):
    __slots__ = ()

    def copy(self) -> FrozenList[T]:
        return FrozenList(self)


class UniqueList[H]:
    __slots__ = ("__data", "__set")

    def __init__(self, items: Iterable[H] = ()) -> None:
        self.__data: list[H] = []
        self.__set: set[H] = set()
        self.extend(items)

    def add(self, item: H) -> bool:
        if item in self.__set:
            return False
        self.__set.add(item)
        self.__data.append(item)
        return True

    def extend(self, items: Iterable[H]) -> None:
        for item in items:
            self.add(item)

    def discard(self, item: H) -> None:
        if item in self.__set:
            self.__set.remove(item)
            self.__data.remove(item)

    def clear(self) -> None:
        self.__set.clear()
        self.__data.clear()

    def copy(self) -> UniqueList[H]:
        return UniqueList(self.__data)

    def __contains__(self, item: object) -> bool:
        return item in self.__set

    def __iter__(self) -> Iterator[H]:
        return iter(self.__data)

    def __len__(self) -> int:
        return len(self.__data)

    @overload
    def __getitem__(self, index: int) -> H: ...

    @overload
    def __getitem__(self, index: slice) -> list[H]: ...

    def __getitem__(self, index: int | slice) -> H | list[H]:
        return self.__data[index]

    def to_list(self) -> list[H]:
        return list(self.__data)


class RingBuffer[T]:
    __slots__ = ("buffer",)

    def __init__(self, size: int) -> None:
        if size <= 0:
            raise ValueError("size must be greater than zero")
        self.buffer: deque[T] = deque(maxlen=size)

    def append(self, item: T) -> None:
        self.buffer.append(item)

    def extend(self, items: Iterable[T]) -> None:
        self.buffer.extend(items)

    def clear(self) -> None:
        self.buffer.clear()

    def copy(self) -> RingBuffer[T]:
        maxlen = self.buffer.maxlen
        if maxlen is None:
            raise RuntimeError("RingBuffer requires a finite maxlen")
        result: RingBuffer[T] = RingBuffer(maxlen)
        result.extend(self.buffer)
        return result

    def __len__(self) -> int:
        return len(self.buffer)

    def __iter__(self) -> Iterator[T]:
        return iter(self.buffer)

    @overload
    def __getitem__(self, index: int) -> T: ...

    @overload
    def __getitem__(self, index: slice) -> list[T]: ...

    def __getitem__(self, index: int | slice) -> T | list[T]:
        return list(self.buffer)[index]

    def to_list(self) -> list[T]:
        return list(self.buffer)


def group_by[T, K](
    items: Iterable[T],
    key: Callable[[T], K],
) -> dict[K, list[T]]:
    result: dict[K, list[T]] = {}
    for item in items:
        result.setdefault(key(item), []).append(item)
    return result


def flatten[T](items: Iterable[Nested[T]]) -> list[T]:
    result: list[T] = []
    for item in items:
        if isinstance(item, (list, tuple, set, frozenset)):
            result.extend(flatten(item))
        else:
            result.append(item)
    return result
