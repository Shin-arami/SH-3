from __future__ import annotations

from collections.abc import Callable
from typing import Any, NoReturn

from .hash import short_id
from .json import dumps
from .logging import error as log_error
from .time import iso

__all__ = [
    "ConfigException",
    "KernelException",
    "PathException",
    "RuntimeException",
    "SH3Exception",
    "SerializationException",
    "ValidationException",
    "is_sh3_exception",
    "raise_config",
    "raise_kernel",
    "raise_path",
    "raise_runtime",
    "raise_serialization",
    "raise_validation",
    "safe_execute",
    "unwrap",
]


class SH3Exception(Exception):  # noqa: N818
    """Base exception for all SH-3 system errors."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.context = context or {}
        self.timestamp = iso(__import__("datetime").datetime.now(__import__("datetime").UTC))
        self.trace_id = short_id(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "code": self.code,
            "context": self.context,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
        }

    def to_json(self) -> str:
        return dumps(self.to_dict(), ensure_ascii=False)


class KernelException(SH3Exception):
    """Core system/kernel level failure."""


class ValidationException(SH3Exception):
    """Input or schema validation failure."""


class RuntimeException(SH3Exception):
    """Runtime execution error."""


class ConfigException(SH3Exception):
    """Configuration-related error."""


class SerializationException(SH3Exception):
    """JSON / object serialization error."""


class PathException(SH3Exception):
    """Filesystem/path-related error."""


def raise_validation(
    message: str,
    context: dict[str, Any] | None = None,
) -> NoReturn:
    raise ValidationException(message, context=context)


def raise_runtime(
    message: str,
    context: dict[str, Any] | None = None,
) -> NoReturn:
    raise RuntimeException(message, context=context)


def raise_kernel(
    message: str,
    context: dict[str, Any] | None = None,
) -> NoReturn:
    raise KernelException(message, context=context)


def raise_config(
    message: str,
    context: dict[str, Any] | None = None,
) -> NoReturn:
    raise ConfigException(message, context=context)


def raise_serialization(
    message: str,
    context: dict[str, Any] | None = None,
) -> NoReturn:
    raise SerializationException(message, context=context)


def raise_path(
    message: str,
    context: dict[str, Any] | None = None,
) -> NoReturn:
    raise PathException(message, context=context)


def safe_execute(
    fn: Callable[..., Any],
    *args: Any,
    default: Any = None,
    logger: bool = True,
    **kwargs: Any,
) -> Any:
    """Executes function safely with structured exception capture."""
    try:
        return fn(*args, **kwargs)
    except SH3Exception as e:
        if logger:
            log_error("SH3Exception occurred", e.to_dict())
        return default
    except Exception as e:
        wrapped = RuntimeException(str(e))
        if logger:
            log_error("Unhandled exception wrapped", wrapped.to_dict())
        return default


def is_sh3_exception(e: Exception) -> bool:
    return isinstance(e, SH3Exception)


def unwrap(e: Exception) -> dict[str, Any]:
    if isinstance(e, SH3Exception):
        return e.to_dict()
    return {
        "message": str(e),
        "type": type(e).__name__,
    }
