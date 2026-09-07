from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, TypeVar

K = TypeVar("K")
V = TypeVar("V")

__all__ = [
    "get_safe",
    "has_path",
    "omit",
    "pick",
    "set_safe",
]


def get_safe[K, V](
    d: Mapping[K, V],
    key: K,
    default: V | None = None,
) -> V | None:
    return d.get(key, default)


def set_safe[K, V](
    d: dict[K, V],
    key: K,
    value: V,
) -> dict[K, V]:
    d[key] = value
    return d


def pick[K, V](
    d: Mapping[K, V],
    keys: Iterable[K],
) -> dict[K, V]:
    return {key: d[key] for key in keys if key in d}


def omit[K, V](
    d: Mapping[K, V],
    keys: Iterable[K],
) -> dict[K, V]:
    excluded = set(keys)
    return {key: value for key, value in d.items() if key not in excluded}


def has_path(
    d: Mapping[str, Any],
    path: str,
    sep: str = ".",
) -> bool:
    if not path:
        return False

    current: Any = d
    for key in path.split(sep):
        if not isinstance(current, Mapping) or key not in current:
            return False
        current = current[key]

    return True
