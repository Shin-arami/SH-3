# utils/__init__.py

from __future__ import annotations

# Common utilities (single source of truth for shared logic)
from .common import (
    apply_if,
    chunk,
    deep_get,
    deep_set,
    ensure_dict,
    ensure_list,
    first,
    identity,
    is_empty,
    is_none,
    merge_dicts,
    normalize_space,
    normalize_str,
    pipe,
    safe_cast,
    to_camel_case,
    to_kebab_case,
    to_pascal_case,
    to_snake_case,
    unique,
)

# Dict utilities
from .dict import (
    get_safe,
    has_path,
    omit,
    pick,
    set_safe,
)

# List utilities
from .list import (
    chunk_list,
    compact,
    filter_list,
    flatten,
    head,
    map_list,
    safe_get,
    tail,
)

# String utilities
from .string import (
    contains,
    ends_with,
    join,
    lower,
    map_words,
    remove_chars,
    replace_all,
    split_and_map,
    starts_with,
    strip,
    truncate,
    upper,
)
from .string import (
    is_empty as str_is_empty,
)

__all__ = [
    "apply_if",
    "chunk",
    "chunk_list",
    "compact",
    "contains",
    "deep_get",
    "deep_set",
    "ends_with",
    "ensure_dict",
    "ensure_list",
    "filter_list",
    "first",
    # List
    "flatten",
    # Dict
    "get_safe",
    "has_path",
    "head",
    "identity",
    "is_empty",
    # Common
    "is_none",
    "join",
    "lower",
    "map_list",
    "map_words",
    "merge_dicts",
    "normalize_space",
    "normalize_str",
    "omit",
    "pick",
    "pipe",
    "remove_chars",
    "replace_all",
    "safe_cast",
    "safe_get",
    "set_safe",
    "split_and_map",
    "starts_with",
    "str_is_empty",
    # String
    "strip",
    "tail",
    "to_camel_case",
    "to_kebab_case",
    "to_pascal_case",
    "to_snake_case",
    "truncate",
    "unique",
    "upper",
]
