"""
SH-3 Complete Edition v1.0
Foundation Layer
Types Subsystem

primitives.py

Kernel primitive immutable objects.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Final

__all__ = [
    # Binary
    "EMPTY_BYTES",
    "EMPTY_FROZENSET",
    "EMPTY_MAPPING",
    # String
    "EMPTY_STRING",
    # Collections
    "EMPTY_TUPLE",
    "FALSE",
    # None
    "NONE",
    "ONE_FLOAT",
    "ONE_INT",
    # Boolean
    "TRUE",
    "ZERO_FLOAT",
    # Numbers
    "ZERO_INT",
    "empty_dict",
    # Factory
    "empty_list",
    "empty_set",
    # Check
    "is_empty",
]

# ==========================================================
# Immutable primitives
# ==========================================================

EMPTY_STRING: Final[str] = ""

EMPTY_BYTES: Final[bytes] = b""

EMPTY_TUPLE: Final[tuple[Any, ...]] = ()

EMPTY_FROZENSET: Final[frozenset[Any]] = frozenset()

EMPTY_MAPPING: Final[MappingProxyType[str, Any]] = MappingProxyType({})

ZERO_INT: Final[int] = 0

ONE_INT: Final[int] = 1

ZERO_FLOAT: Final[float] = 0.0

ONE_FLOAT: Final[float] = 1.0

TRUE: Final[bool] = True

FALSE: Final[bool] = False

NONE: Final[None] = None

# ==========================================================
# Mutable factories
# ==========================================================


def empty_list() -> list[Any]:
    """
    Return a new empty list.
    """
    return []


def empty_dict() -> dict[str, Any]:
    """
    Return a new empty dict.
    """
    return {}


def empty_set() -> set[Any]:
    """
    Return a new empty set.
    """
    return set()


# ==========================================================
# Utility
# ==========================================================


def is_empty(value: Any) -> bool:
    """
    Generic empty check.
    """

    if value is None:
        return True

    try:
        return len(value) == 0
    except TypeError:
        return False
