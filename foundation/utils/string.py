# utils/string.py

from __future__ import annotations

from collections.abc import Callable, Iterable

from .common import (
    normalize_space,
    normalize_str,
)

# ----------------------------
# Normalization
# ----------------------------


def strip(s: str) -> str:
    return normalize_str(s)


def lower(s: str) -> str:
    return normalize_str(s).lower()


def upper(s: str) -> str:
    return normalize_str(s).upper()


# ----------------------------
# Validation / Inspection
# ----------------------------


def is_empty(s: str) -> bool:
    return normalize_str(s) == ""


def contains(s: str, sub: str) -> bool:
    return normalize_str(sub) in normalize_str(s)


def starts_with(s: str, prefix: str) -> bool:
    return normalize_str(s).startswith(normalize_str(prefix))


def ends_with(s: str, suffix: str) -> bool:
    return normalize_str(s).endswith(normalize_str(suffix))


# ----------------------------
# Transform Utilities
# ----------------------------


def truncate(s: str, length: int, suffix: str = "...") -> str:
    s = normalize_str(s)
    if length <= 0:
        return ""
    if len(s) <= length:
        return s
    return s[:length] + suffix


def replace_all(s: str, old: str, new: str) -> str:
    return normalize_str(s).replace(old, new)


def remove_chars(s: str, chars: str) -> str:
    table = {ord(c): None for c in chars}
    return normalize_str(s).translate(table)


# ----------------------------
# Functional Helpers
# ----------------------------


def map_words(s: str, fn: Callable[[str], str]) -> str:
    return " ".join(fn(w) for w in normalize_space(s).split())


def split_and_map(s: str, sep: str, fn: Callable[[str], str]) -> list[str]:
    return [fn(x) for x in normalize_str(s).split(sep)]


def join(iterable: Iterable[str], sep: str = " ") -> str:
    return sep.join(normalize_str(x) for x in iterable)
