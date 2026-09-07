from __future__ import annotations

from types import UnionType
from typing import Any, TypeVar, Union, get_args, get_origin, get_type_hints

T = TypeVar("T")

__all__ = [
    "Typed",
    "assert_protocol",
    "get_function_hints",
    "get_origin_type",
    "get_type_args",
    "implements_protocol",
    "is_callable_type",
    "is_generic",
    "is_optional",
    "is_union",
    "type_name",
]

def get_origin_type(t: Any) -> Any:
    """Get origin type from generic."""
    origin = get_origin(t)
    return origin if origin is not None else t

def get_type_args(t: Any) -> tuple[Any, ...]:
    """Get type arguments from generic."""
    return get_args(t)

def type_name(t: type[Any]) -> str:
    """Get readable type name."""
    name = getattr(t, "__name__", None)
    return name if isinstance(name, str) else str(t)

def is_generic(t: Any) -> bool:
    """Check if type is generic."""
    return get_origin(t) is not None

def is_union(t: Any) -> bool:
    """Check if type is Union."""
    origin = get_origin(t)
    return origin is Union or origin is UnionType

def is_optional(t: Any) -> bool:
    """Check if type is Optional."""
    return is_union(t) and type(None) in get_type_args(t)

def is_callable_type(obj: Any) -> bool:
    """Check if object is callable."""
    return callable(obj)

def get_function_hints(fn: Any) -> dict[str, Any]:
    """Get type hints from function."""
    try:
        return get_type_hints(fn)
    except Exception:
        return {}

class Typed[T]:
    """Base class for typed generic objects."""

    __type__: type[T] | None = None

    @classmethod
    def of(cls, value_type: type[T]) -> type[Typed[T]]:
        """Create a typed variant."""
        return _create_typed_class(value_type)

def _create_typed_class[T](value_type: type[T]) -> type[Typed[T]]:
    """Create a runtime typed variant."""
    return type(
        "TypedVariant",
        (Typed,),
        {"__type__": value_type},
    )

def implements_protocol(
    obj: Any,
    protocol_methods: list[str],
) -> bool:
    """Check if object implements protocol."""
    return all(
        hasattr(obj, method) and callable(getattr(obj, method))
        for method in protocol_methods
    )

def assert_protocol(
    obj: Any,
    protocol_methods: list[str],
    name: str = "object",
) -> None:
    """Assert object implements protocol."""
    if not implements_protocol(obj, protocol_methods):
        raise TypeError(f"{name} does not implement required protocol")
