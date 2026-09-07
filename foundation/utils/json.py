from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

__all__ = [
    "compact",
    "dumps",
    "is_valid_json",
    "loads",
    "normalize",
    "pretty",
    "safe_dumps",
    "safe_loads",
    "to_dict",
]


# ----------------------------
# Core Serialization
# ----------------------------

def dumps(
    obj: Any,
    ensure_ascii: bool = False,
    indent: int | None = None,
    sort_keys: bool = False,
) -> str:
    return json.dumps(
        obj,
        ensure_ascii=ensure_ascii,
        indent=indent,
        sort_keys=sort_keys,
    )


def loads(s: str) -> Any:
    return json.loads(s)


# ----------------------------
# Safe Variants
# ----------------------------

def safe_dumps(
    obj: Any,
    default: Any = None,
    ensure_ascii: bool = False,
    indent: int | None = None,
) -> str:
    try:
        return json.dumps(
            obj,
            ensure_ascii=ensure_ascii,
            indent=indent,
        )
    except Exception:
        return "" if default is None else str(default)


def safe_loads(s: str, default: Any = None) -> Any:
    try:
        return json.loads(s)
    except Exception:
        return default


# ----------------------------
# Dict Helpers
# ----------------------------

def to_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return {str(key): value for key, value in obj.items()}

    obj_dict = getattr(obj, "__dict__", None)
    if isinstance(obj_dict, Mapping):
        return {str(key): value for key, value in obj_dict.items()}

    to_dict_method = getattr(obj, "to_dict", None)
    if callable(to_dict_method):
        result: Any = to_dict_method()
        if isinstance(result, Mapping):
            return {str(key): value for key, value in result.items()}

    raise TypeError("Object is not JSON serializable to dict")


def normalize(obj: Any) -> Any:
    """
    Converts common non-serializable structures into JSON-safe equivalents.
    """
    if obj is None:
        return None

    if isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, Mapping):
        return {
            str(key): normalize(value)
            for key, value in obj.items()
        }

    if isinstance(obj, (list, tuple, set, frozenset)):
        return [normalize(item) for item in obj]

    obj_dict = getattr(obj, "__dict__", None)
    if isinstance(obj_dict, Mapping):
        return normalize(obj_dict)

    return str(obj)


# ----------------------------
# Pretty / Compact Control
# ----------------------------

def pretty(obj: Any, indent: int = 2) -> str:
    return json.dumps(
        obj,
        indent=indent,
        ensure_ascii=False,
    )


def compact(obj: Any) -> str:
    return json.dumps(
        obj,
        separators=(",", ":"),
        ensure_ascii=False,
    )


# ----------------------------
# Validation
# ----------------------------

def is_valid_json(s: str) -> bool:
    try:
        json.loads(s)
        return True
    except Exception:
        return False
