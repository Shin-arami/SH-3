from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from typing import Any, TypeVar

# T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


def is_none(x: Any) -> bool:
    return x is None


def is_empty(x: Any) -> bool:
    if x is None:
        return True
    if isinstance(x, (str, list, tuple, set, dict)):
        return len(x) == 0
    return False


def ensure_list(x: Any) -> list[Any]:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    if isinstance(x, (tuple, set)):
        return list(x)
    return [x]


def ensure_dict(x: Any) -> dict[Any, Any]:
    if x is None:
        return {}
    if isinstance(x, dict):
        return x
    raise TypeError("Expected dict-like object")


def safe_cast[T](
    fn: Callable[[Any], T],
    value: Any,
    default: T | None = None,
) -> T | None:
    try:
        return fn(value)
    except (TypeError, ValueError):
        return default


def first[T](
    iterable: Iterable[T],
    default: T | None = None,
) -> T | None:
    for item in iterable:
        return item
    return default


def unique[T](iterable: Iterable[T]) -> list[T]:
    seen: set[T] = set()
    out: list[T] = []
    for x in iterable:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def chunk[T](iterable: Iterable[T], size: int) -> Iterator[tuple[T, ...]]:
    if size <= 0:
        raise ValueError("size must be > 0")
    buf: list[T] = []
    for x in iterable:
        buf.append(x)
        if len(buf) == size:
            yield tuple(buf)
            buf = []
    if buf:
        yield tuple(buf)


def deep_get(
    d: Mapping[Any, Any],
    path: str,
    default: Any = None,
    sep: str = ".",
) -> Any:
    if not isinstance(d, Mapping):
        return default
    cur: Any = d
    for key in path.split(sep):
        if not isinstance(cur, Mapping) or key not in cur:
            return default
        cur = cur[key]
    return cur


def deep_set(
    d: dict[Any, Any],
    path: str,
    value: Any,
    sep: str = ".",
) -> dict[Any, Any]:
    if not isinstance(d, dict):
        raise TypeError("Expected dict")
    cur = d
    keys = path.split(sep)
    for k in keys[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    cur[keys[-1]] = value
    return d


def merge_dicts(*dicts: Mapping[Any, Any]) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for d in dicts:
        if not isinstance(d, Mapping):
            continue
        for k, v in d.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, Mapping):
                result[k] = merge_dicts(result[k], v)
            else:
                result[k] = v
    return result


def normalize_str(s: Any) -> str:
    if s is None:
        return ""
    return str(s).strip()


def normalize_space(s: str) -> str:
    s = normalize_str(s)
    return " ".join(s.split())


def to_snake_case(s: str) -> str:
    s = normalize_str(s)
    out: list[str] = []
    for i, c in enumerate(s):
        if c.isupper() and i > 0:
            out.append("_")
        out.append(c.lower())
    return "".join(out).replace(" ", "_")


def to_kebab_case(s: str) -> str:
    return to_snake_case(s).replace("_", "-")


def to_camel_case(s: str) -> str:
    s = normalize_space(s)
    parts = s.split(" ")
    if not parts:
        return ""
    return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])


def to_pascal_case(s: str) -> str:
    s = normalize_space(s)
    return "".join(p.capitalize() for p in s.split(" ") if p)


def identity[T](x: T) -> T:
    return x


def apply_if[T](
    value: T,
    predicate: Callable[[T], bool],
    fn: Callable[[T], T],
) -> T:
    return fn(value) if predicate(value) else value


def pipe(value: Any, *fns: Callable[[Any], Any]) -> Any:
    for fn in fns:
        value = fn(value)
    return value
