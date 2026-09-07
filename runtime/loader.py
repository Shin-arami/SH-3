from __future__ import annotations

import importlib
import inspect
from collections.abc import Callable
from threading import RLock
from types import ModuleType
from typing import Any, cast

from foundation.utils.exceptions import RuntimeException, safe_execute
from foundation.utils.logging import error, info

__all__ = [
    "cached_load",
    "clear_cache",
    "execute_function",
    "get_attr",
    "load_class",
    "load_function",
    "load_module",
]

_CACHE_LOCK = RLock()
_LOADED_CACHE: dict[str, ModuleType] = {}


def _validate_name(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value:
        raise ValueError(f"{name} must not be empty")
    return value


def load_module(module_path: str) -> ModuleType:
    module_path = _validate_name(module_path, "module_path")
    try:
        module = importlib.import_module(module_path)
        info("Module loaded", {"module": module_path})
        return module
    except Exception as exc:
        wrapped = RuntimeException(f"Module load failed: {module_path} | {exc}")
        error("Module load error", wrapped.to_dict())
        raise wrapped from exc


def get_attr(module: Any, attr: str) -> Any:
    attr = _validate_name(attr, "attr")
    if not hasattr(module, attr):
        raise RuntimeException(f"Attribute not found: {attr}")
    return getattr(module, attr)


def load_function(
    module_path: str,
    func_name: str,
) -> Callable[..., Any]:
    module_path = _validate_name(module_path, "module_path")
    func_name = _validate_name(func_name, "func_name")
    module = load_module(module_path)
    fn = get_attr(module, func_name)
    if not callable(fn):
        raise RuntimeException(f"{func_name} is not callable in {module_path}")
    info(
        "Function loaded",
        {"module": module_path, "function": func_name},
    )
    return cast(Callable[..., Any], fn)


def load_class(
    module_path: str,
    class_name: str,
) -> type[Any]:
    module_path = _validate_name(module_path, "module_path")
    class_name = _validate_name(class_name, "class_name")
    module = load_module(module_path)
    cls = get_attr(module, class_name)
    if not inspect.isclass(cls):
        raise RuntimeException(f"{class_name} is not a class in {module_path}")
    info(
        "Class loaded",
        {"module": module_path, "class": class_name},
    )
    return cls


def execute_function(
    module_path: str,
    func_name: str,
    *args: Any,
    **kwargs: Any,
) -> Any:
    fn = load_function(module_path, func_name)

    def _run() -> Any:
        return fn(*args, **kwargs)

    try:
        return safe_execute(_run)
    except Exception as exc:
        error("Function execution failed", {"error": str(exc)})
        raise


def cached_load(module_path: str) -> ModuleType:
    module_path = _validate_name(module_path, "module_path")

    with _CACHE_LOCK:
        cached = _LOADED_CACHE.get(module_path)
        if cached is not None:
            return cached

    module = load_module(module_path)

    with _CACHE_LOCK:
        existing = _LOADED_CACHE.get(module_path)
        if existing is not None:
            return existing
        _LOADED_CACHE[module_path] = module
        return module


def clear_cache() -> None:
    with _CACHE_LOCK:
        _LOADED_CACHE.clear()
    info("Loader cache cleared")
