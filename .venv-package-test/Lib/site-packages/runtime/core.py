from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import Any, TypeVar

from foundation.utils.exceptions import RuntimeException, SH3Exception, safe_execute
from foundation.utils.logging import error, info

from .context_manager import ContextManager, RuntimeContext

__all__ = ["ContextManager", "RuntimeContext", "RuntimeCore"]

T = TypeVar("T")


class RuntimeCore:
    __slots__ = ("_lock", "context", "context_manager", "hooks", "name")

    def __init__(
        self,
        name: str = "sh3-runtime",
        context_manager: ContextManager | None = None,
    ) -> None:
        if not name or not name.strip():
            raise ValueError("name must not be empty")
        self.name = name
        self.context_manager = context_manager or ContextManager()
        self.context = RuntimeContext(name)
        self.hooks: dict[str, Callable[..., Any]] = {}
        self._lock = RLock()

    def register_hook(self, event: str, fn: Callable[..., Any]) -> None:
        if not event or not event.strip():
            raise ValueError("event must not be empty")
        if not callable(fn):
            raise TypeError("fn must be callable")
        with self._lock:
            self.hooks[event] = fn
        info("Hook registered", {"event": event})

    def unregister_hook(self, event: str) -> bool:
        with self._lock:
            return self.hooks.pop(event, None) is not None

    def _get_hook(self, event: str) -> Callable[..., Any] | None:
        with self._lock:
            return self.hooks.get(event)

    def _trigger(self, event: str, payload: dict[str, Any]) -> None:
        hook = self._get_hook(event)
        if hook is not None:
            safe_execute(hook, payload)

    @staticmethod
    def _callable_name(fn: Callable[..., Any]) -> str:
        return getattr(fn, "__name__", type(fn).__name__)

    def run(
        self,
        fn: Callable[..., T],
        *args: Any,
        context: RuntimeContext | None = None,
        **kwargs: Any,
    ) -> T:
        if not callable(fn):
            raise TypeError("fn must be callable")
        ctx = context or self.context
        name = self._callable_name(fn)
        self._trigger(
            "before_run",
            {"function": name, "context": ctx.to_dict()},
        )
        info(
            "Runtime execution started",
            {"function": name, "trace_id": ctx.trace_id},
        )
        try:
            result = fn(*args, **kwargs)
        except SH3Exception as exc:
            error("SH3Exception in runtime", exc.to_dict())
            raise
        except Exception as exc:
            wrapped = RuntimeException(str(exc))
            error("Unhandled runtime exception", wrapped.to_dict())
            raise wrapped from exc
        self._trigger("after_run", {"result": str(result)})
        return result

    def pipe(
        self,
        value: Any,
        *fns: Callable[[Any], Any],
        context: RuntimeContext | None = None,
    ) -> Any:
        ctx = context or self.context
        current = value
        for fn in fns:
            if not callable(fn):
                raise TypeError("pipeline function must be callable")
            name = self._callable_name(fn)
            self._trigger(
                "before_pipe",
                {
                    "function": name,
                    "value": str(current),
                    "trace_id": ctx.trace_id,
                },
            )
            info("Pipeline step", {"function": name, "trace_id": ctx.trace_id})
            current = self.run(fn, current, context=ctx)
        self._trigger(
            "after_pipe",
            {"value": str(current), "trace_id": ctx.trace_id},
        )
        return current

    def set_state(self, key: str, value: Any) -> None:
        self.context.set(key, value)
        info("State updated", {"key": key})

    def get_state(self, key: str, default: Any = None) -> Any:
        return self.context.get(key, default)

    def push_context(self, name: str = "runtime") -> RuntimeContext:
        return self.context_manager.push(name)

    def pop_context(self) -> RuntimeContext | None:
        return self.context_manager.pop()

    def current_context(self) -> RuntimeContext | None:
        return self.context_manager.current()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            hooks = list(self.hooks)
        return {
            "name": self.name,
            "context": self.context.to_dict(),
            "context_manager": self.context_manager.snapshot(),
            "hooks": hooks,
        }
