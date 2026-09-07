from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from typing import Any, TypeVar

from .common import first

T = TypeVar("T")
R = TypeVar("R")


def flatten(items: Iterable[Any]) -> list[Any]:
    out: list[Any] = []
    for x in items:
        if isinstance(x, (list, tuple, set)):
            out.extend(x)
        else:
            out.append(x)
    return out


def safe_get[T](
    lst: list[T],
    index: int,
    default: T | None = None,
) -> T | None:
    if not isinstance(lst, list):
        return default
    if index < 0 or index >= len(lst):
        return default
    return lst[index]


def chunk_list[T](lst: Iterable[T], size: int) -> Iterator[list[T]]:
    if size <= 0:
        raise ValueError("size must be > 0")
    buf: list[T] = []
    for x in lst:
        buf.append(x)
        if len(buf) == size:
            yield buf
            buf = []
    if buf:
        yield buf


def head[T](
    lst: Iterable[T],
    default: T | None = None,
) -> T | None:
    return first(lst, default)


def tail[T](lst: list[T]) -> list[T]:
    if not lst:
        return []
    return lst[1:]


def compact(lst: Iterable[Any]) -> list[Any]:
    out: list[Any] = []
    for x in lst:
        if x is None:
            continue
        if isinstance(x, str) and x == "":
            continue
        out.append(x)
    return out


def map_list[T, R](
    lst: Iterable[T],
    fn: Callable[[T], R],
) -> list[R]:
    return [fn(x) for x in lst]


def filter_list[T](
    lst: Iterable[T],
    fn: Callable[[T], bool],
) -> list[T]:
    return [x for x in lst if fn(x)]
