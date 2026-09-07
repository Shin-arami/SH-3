from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from typing import Any, TypeVar

from foundation.utils.exceptions import RuntimeException, SH3Exception
from foundation.utils.logging import error, info
from runtime.context_manager import RuntimeContext

T = TypeVar("T")

__all__ = ["ExecutionResult", "RuntimeExecutor"]


@dataclass(frozen=True, slots=True)
class ExecutionResult[T]:
    value: T
    trace_id: str
    function: str

    @property
    def succeeded(self) -> bool:
        return True


class RuntimeExecutor:
    __slots__ = ("_lock",)

    def __init__(self) -> None:
        self._lock = RLock()

    @staticmethod
    def _function_name(fn: Callable[..., Any]) -> str:
        return getattr(fn, "__name__", type(fn).__name__)

    def execute(
        self,
        fn: Callable[..., T],
        *args: Any,
        context: RuntimeContext | None = None,
        **kwargs: Any,
    ) -> ExecutionResult[T]:
        if not callable(fn):
            raise RuntimeException("Execution target is not callable")

        function = self._function_name(fn)
        trace_id = context.trace_id if context is not None else ""

        info(
            "Runtime executor started",
            {"function": function, "trace_id": trace_id},
        )

        with self._lock:
            try:
                value = fn(*args, **kwargs)
            except SH3Exception as exc:
                error("SH3Exception in executor", exc.to_dict())
                raise
            except Exception as exc:
                wrapped = RuntimeException(str(exc))
                error("Unhandled executor exception", wrapped.to_dict())
                raise wrapped from exc

        return ExecutionResult(
            value=value,
            trace_id=trace_id,
            function=function,
        )

    def run(
        self,
        fn: Callable[..., T],
        *args: Any,
        context: RuntimeContext | None = None,
        **kwargs: Any,
    ) -> T:
        return self.execute(
            fn,
            *args,
            context=context,
            **kwargs,
        ).value
