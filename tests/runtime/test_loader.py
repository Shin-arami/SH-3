from __future__ import annotations

import pytest

from foundation.utils.exceptions import RuntimeException
from runtime.loader import (
    cached_load,
    clear_cache,
    execute_function,
    get_attr,
    load_class,
    load_function,
    load_module,
)


def test_load_module() -> None:
    module = load_module("math")
    assert module.__name__ == "math"


def test_get_attr() -> None:
    module = load_module("math")
    assert get_attr(module, "sqrt") is module.sqrt


def test_get_attr_missing() -> None:
    module = load_module("math")
    with pytest.raises(RuntimeException):
        get_attr(module, "missing_attribute")


def test_load_function() -> None:
    function = load_function("builtins", "len")
    assert callable(function)
    assert function([1, 2, 3]) == 3


def test_load_function_rejects_non_callable() -> None:
    with pytest.raises(RuntimeException):
        load_function("builtins", "__doc__")


def test_load_class() -> None:
    cls = load_class("builtins", "dict")
    assert cls is dict


def test_load_class_rejects_non_class() -> None:
    with pytest.raises(RuntimeException):
        load_class("builtins", "len")


def test_execute_function() -> None:
    result = execute_function("builtins", "len", [1, 2, 3])
    assert result == 3


def test_load_module_failure() -> None:
    with pytest.raises(RuntimeException):
        load_module("sh3_module_that_does_not_exist")


def test_cached_load_returns_same_module() -> None:
    clear_cache()
    first = cached_load("math")
    second = cached_load("math")
    assert first is second


def test_clear_cache() -> None:
    clear_cache()
    first = cached_load("math")
    clear_cache()
    second = cached_load("math")
    assert first is second
