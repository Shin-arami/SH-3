from __future__ import annotations

import os
from collections.abc import Callable

# ----------------------------
# Normalization
# ----------------------------

def normalize(path: str) -> str:
    if not path:
        return ""
    return os.path.normpath(path)


def to_posix(path: str) -> str:
    return normalize(path).replace("\\", "/")


def to_windows(path: str) -> str:
    return normalize(path).replace("/", "\\")


def abs_path(path: str) -> str:
    if not path:
        return ""
    return os.path.abspath(path)


# ----------------------------
# Path Composition
# ----------------------------

def join(*parts: str) -> str:
    return os.path.normpath(os.path.join(*parts))


def concat(base: str, *parts: str) -> str:
    return join(base, *parts)


def dirname(path: str) -> str:
    return os.path.dirname(normalize(path))


def basename(path: str) -> str:
    return os.path.basename(normalize(path))


def split_ext(path: str) -> tuple[str, str]:
    return os.path.splitext(normalize(path))


# ----------------------------
# Path Inspection
# ----------------------------

def exists(path: str) -> bool:
    return os.path.exists(path)


def is_file(path: str) -> bool:
    return os.path.isfile(path)


def is_dir(path: str) -> bool:
    return os.path.isdir(path)


def is_abs(path: str) -> bool:
    return os.path.isabs(path)


# ----------------------------
# Path Analysis
# ----------------------------

def depth(path: str) -> int:
    p = normalize(path)
    if not p:
        return 0
    return len([x for x in p.split(os.sep) if x])


def parts(path: str) -> list[str]:
    p = normalize(path)
    return [x for x in p.split(os.sep) if x]


def parent(path: str, levels: int = 1) -> str:
    p = normalize(path)
    for _ in range(max(0, levels)):
        p = os.path.dirname(p)
    return p


# ----------------------------
# Path Building
# ----------------------------

def with_suffix(path: str, suffix: str) -> str:
    base, _ = os.path.splitext(normalize(path))
    if suffix and not suffix.startswith("."):
        suffix = "." + suffix
    return base + suffix


def replace_root(path: str, old: str, new: str) -> str:
    p = normalize(path)
    old_n = normalize(old)
    if p.startswith(old_n):
        return join(new, p[len(old_n):].lstrip(os.sep))
    return p


# ----------------------------
# Functional Utilities
# ----------------------------

def map_parts(path: str, fn: Callable[[str], str]) -> str:
    p = normalize(path)
    return join(*(fn(x) for x in p.split(os.sep) if x))


def filter_parts(path: str, fn: Callable[[str], bool]) -> str:
    p = normalize(path)
    return join(*(x for x in p.split(os.sep) if fn(x)))
