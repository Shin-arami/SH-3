from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from .common import is_empty


def is_type(value: Any, t: type[Any] | tuple[type[Any], ...]) -> bool:
    return isinstance(value, t)


def is_str(value: Any) -> bool:
    return isinstance(value, str)


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_float(value: Any) -> bool:
    return isinstance(value, float)


def is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def is_numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_iterable(value: Any) -> bool:
    return isinstance(value, Iterable) and not isinstance(value, (str, bytes))


def not_none(value: Any) -> bool:
    return value is not None


def not_empty(value: Any) -> bool:
    return not is_empty(value)


def required(value: Any, name: str = "value") -> Any:
    if value is None:
        raise ValueError(f"{name} is required")
    return value


def in_range(value: int | float, min_v: float, max_v: float) -> bool:
    return min_v <= value <= max_v


def min_value(value: int | float, min_v: float) -> bool:
    return value >= min_v


def max_value(value: int | float, max_v: float) -> bool:
    return value <= max_v


def min_length(value: str, length: int) -> bool:
    return isinstance(value, str) and len(value) >= length


def max_length(value: str, length: int) -> bool:
    return isinstance(value, str) and len(value) <= length


def length_between(value: str, min_l: int, max_l: int) -> bool:
    return isinstance(value, str) and min_l <= len(value) <= max_l


def contains(value: Iterable[Any], item: Any) -> bool:
    if not is_iterable(value):
        return False
    return item in value


def all_match(
    values: Iterable[Any],
    fn: Callable[[Any], bool],
) -> bool:
    return all(fn(v) for v in values)


def any_match(
    values: Iterable[Any],
    fn: Callable[[Any], bool],
) -> bool:
    return any(fn(v) for v in values)


def has_keys(d: Mapping[str, Any], keys: Iterable[str]) -> bool:
    if not isinstance(d, dict):
        return False
    return all(k in d for k in keys)


def schema_check(
    d: Mapping[str, Any],
    schema: Mapping[str, type[Any] | tuple[type[Any], ...]],
) -> bool:
    if not isinstance(d, dict):
        return False
    for k, t in schema.items():
        if k not in d:
            return False
        if not isinstance(d[k], t):
            return False
    return True


def validate(
    value: Any,
    *checks: Callable[[Any], bool],
) -> bool:
    return all(check(value) for check in checks)


def assert_valid(
    value: Any,
    *checks: Callable[[Any], bool],
    name: str = "value",
) -> Any:
    if not validate(value, *checks):
        raise ValueError(f"{name} validation failed")
    return value
