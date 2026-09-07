# foundation/__init__.py

from __future__ import annotations

# Utils - Core (most commonly needed)
from .utils.common import (
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

# Utils - Collections
from .utils.dict import get_safe, has_path, omit, pick, set_safe

# Exceptions
from .utils.exceptions import (
    ConfigException,
    KernelException,
    PathException,
    RuntimeException,
    SerializationException,
    SH3Exception,
    ValidationException,
    raise_config,
    raise_kernel,
    raise_runtime,
    raise_validation,
    safe_execute,
)
from .utils.hash import hash_object, md5, nonce, random_id, sha256, short_id, stable_id

# Utils - Advanced Modules
from .utils.json import dumps, is_valid_json, loads, pretty
from .utils.json import safe_loads as parse_safe
from .utils.list import chunk_list, compact, filter_list, flatten, head, map_list, safe_get, tail
from .utils.logging import debug, error, event, get_logger, info, warn
from .utils.object import SH3Object, from_dict, from_json, to_dict, to_json
from .utils.path import basename, dirname, exists, is_abs, is_dir, is_file
from .utils.path import join as path_join
from .utils.path import normalize as path_normalize
from .utils.string import (
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
from .utils.time import add_days, format_datetime, is_future, is_past, iso, now_local, now_utc
from .utils.typing import get_origin_type, get_type_args, is_generic, is_optional
from .utils.validate import is_bool, is_int, is_numeric, is_str, not_empty, not_none, required

__all__ = [
    "ConfigException",
    "KernelException",
    "PathException",
    "RuntimeException",
    # Exceptions
    "SH3Exception",
    "SH3Object",
    "SerializationException",
    "ValidationException",
    "add_days",
    "apply_if",
    "basename",
    "chunk",
    "chunk_list",
    "compact",
    "contains",
    "debug",
    "deep_get",
    "deep_set",
    "dirname",
    # Advanced
    "dumps",
    "ends_with",
    "ensure_dict",
    "ensure_list",
    "error",
    "event",
    "exists",
    "filter_list",
    "first",
    "flatten",
    "format_datetime",
    "from_dict",
    "from_json",
    "get_logger",
    "get_origin_type",
    # Collections
    "get_safe",
    "get_type_args",
    "has_path",
    "hash_object",
    "head",
    "identity",
    "info",
    "is_abs",
    "is_bool",
    "is_dir",
    "is_empty",
    "is_file",
    "is_future",
    "is_generic",
    "is_int",
    # Common utilities
    "is_none",
    "is_numeric",
    "is_optional",
    "is_past",
    "is_str",
    "is_valid_json",
    "iso",
    "join",
    "loads",
    "lower",
    "map_list",
    "map_words",
    "md5",
    "merge_dicts",
    "nonce",
    "normalize_space",
    "normalize_str",
    "not_empty",
    "not_none",
    "now_local",
    "now_utc",
    "omit",
    "parse_safe",
    "path_join",
    "path_normalize",
    "pick",
    "pipe",
    "pretty",
    "raise_config",
    "raise_kernel",
    "raise_runtime",
    "raise_validation",
    "random_id",
    "remove_chars",
    "replace_all",
    "required",
    "safe_cast",
    "safe_execute",
    "safe_get",
    "set_safe",
    "sha256",
    "short_id",
    "split_and_map",
    "stable_id",
    "starts_with",
    "strip",
    "tail",
    "to_camel_case",
    "to_dict",
    "to_json",
    "to_kebab_case",
    "to_pascal_case",
    "to_snake_case",
    "truncate",
    "unique",
    "upper",
    "warn",
]
