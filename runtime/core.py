from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import Any, TypeVar

from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.types.identifiers import IdentifierGenerator
from foundation.utils.exceptions import RuntimeException, SH3Exception, safe_execute
from foundation.utils.logging import error, info
from infrastructure.event_bus import EventPublisher
from infrastructure.events.model import Event
from infrastructure.events.propagation import EventPropagationContext

from .context_manager import ContextManager, RuntimeContext

__all__ = ["ContextManager", "RuntimeContext", "RuntimeCore"]

T = TypeVar("T")


class _ExecutionFailureError(Exception):
    __slots__ = ("exception", "propagation")

    def __init__(
        self,
        exception: Exception,
        propagation: EventPropagationContext,
    ) -> None:
        super().__init__(str(exception))
        self.exception = exception
        self.propagation = propagation


class RuntimeCore:
    __slots__ = (
        "_event_publisher",
        "_lock",
        "_state",
        "context",
        "context_manager",
        "hooks",
        "name",
    )
    def __init__(
        self,
        name: str = "sh3-runtime",
        context_manager: ContextManager | None = None,
        *,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        if not name or not name.strip():
            raise ValueError("name must not be empty")
        self.name = name
        self.context_manager = context_manager or ContextManager()
        self.context = RuntimeContext(name)
        self.hooks: dict[str, Callable[..., Any]] = {}
        self._event_publisher = event_publisher
        self._lock = RLock()
        self._state: dict[str, Any] = {}

    @property
    def event_publisher(self) -> EventPublisher | None:
        return self._event_publisher

    def set_event_publisher(self, publisher: EventPublisher | None) -> None:
        self._event_publisher = publisher

    def register_hook(self, event: str, callback: Callable[..., Any]) -> None:
        if not event or not event.strip():
            raise ValueError("event must not be empty")
        if not callable(callback):
            raise TypeError("callback must be callable")
        with self._lock:
            self.hooks[event] = callback
        info("Hook registered", {"event": event})

    def remove_hook(self, event: str) -> None:
        with self._lock:
            self.hooks.pop(event, None)

    def _trigger(self, event: str, payload: dict[str, Any]) -> None:
        with self._lock:
            hook = self.hooks.get(event)
        if hook is not None:
            safe_execute(hook, payload)

    def _publish(
        self,
        event_name: str,
        event_type: EventType,
        category: Category,
        payload: dict[str, Any],
        propagation: EventPropagationContext,
    ) -> EventPropagationContext:
        event = Event.create(
            event_name=event_name,
            producer=self.name,
            payload=payload,
            category=category,
            event_type=event_type,
            correlation_id=propagation.correlation_id,
            causation_id=propagation.causation_id,
            trace_id=propagation.trace_id,
            tenant_id=propagation.tenant_id,
        )
        publisher = self._event_publisher
        if publisher is not None:
            try:
                publisher.publish(event)
            except Exception as exc:
                error(
                    "Runtime event publication failed",
                    {"event": event_name, "error": str(exc)},
                )
        return propagation.next(event.metadata.event_id)

    def _new_propagation(
        self,
        correlation_id: str,
        trace_id: str | None,
        *,
        causation_id: str | None = None,
        tenant_id: str | None = None,
    ) -> EventPropagationContext:
        return EventPropagationContext.create(
            correlation_id,
            causation_id=causation_id,
            trace_id=trace_id,
            tenant_id=tenant_id,
        )

    def _run_with_propagation(
        self,
        fn: Callable[..., T],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        propagation: EventPropagationContext | None = None,
        *,
        context: RuntimeContext | None = None,
    ) -> tuple[T, EventPropagationContext]:
        ctx = context or self.context
        execution_id = IdentifierGenerator.entity()
        current = propagation or self._new_propagation(
            execution_id,
            ctx.trace_id,
        )
        function_name = getattr(fn, "__name__", type(fn).__name__)

        self._trigger(
            "before_run",
            {
                "function": function_name,
                "context": ctx.to_dict(),
            },
        )
        info(
            "Runtime execution started",
            {
                "function": function_name,
                "trace_id": ctx.trace_id,
            },
        )

        current = self._publish(
            "RuntimeExecutionStarted",
            EventType.START,
            Category.EXECUTION,
            {
                "execution_id": execution_id,
                "component": function_name,
                "trace_id": ctx.trace_id,
            },
            current,
        )

        try:
            result = fn(*args, **kwargs)
            self._trigger("after_run", {"result": str(result)})
            current = self._publish(
                "RuntimeExecutionCompleted",
                EventType.COMPLETE,
                Category.EXECUTION,
                {
                    "execution_id": execution_id,
                    "component": function_name,
                    "result": result,
                    "success": True,
                    "trace_id": ctx.trace_id,
                },
                current,
            )
            return result, current
        except SH3Exception as exc:
            error("SH3Exception in runtime", exc.to_dict())
            current = self._publish(
                "RuntimeExecutionFailed",
                EventType.FAILURE,
                Category.EXECUTION,
                {
                    "execution_id": execution_id,
                    "component": function_name,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "success": False,
                    "trace_id": ctx.trace_id,
                },
                current,
            )
            raise _ExecutionFailureError(exc, current) from exc
        except Exception as exc:
            wrapped = RuntimeException(str(exc))
            error("Unhandled runtime exception", wrapped.to_dict())
            current = self._publish(
                "RuntimeExecutionFailed",
                EventType.FAILURE,
                Category.EXECUTION,
                {
                    "execution_id": execution_id,
                    "component": function_name,
                    "error": str(wrapped),
                    "error_type": type(wrapped).__name__,
                    "success": False,
                    "trace_id": ctx.trace_id,
                },
                current,
            )
            raise _ExecutionFailureError(wrapped, current) from exc

    def run(
        self,
        fn: Callable[..., T],
        *args: Any,
        context: RuntimeContext | None = None,
        propagation: EventPropagationContext | None = None,
        **kwargs: Any,
    ) -> T:
        try:
            result, _ = self._run_with_propagation(
                fn,
                args,
                kwargs,
                propagation=propagation,
                context=context,
            )
            return result
        except _ExecutionFailureError as failure:
            raise failure.exception from failure.exception.__cause__


    def pipe(
        self,
        value: Any,
        *functions: Callable[[Any], Any],
        context: RuntimeContext | None = None,
        propagation: EventPropagationContext | None = None,
    ) -> Any:
        if not functions:
            return value

        ctx = context or self.context
        pipeline_id = IdentifierGenerator.entity()

        self._trigger(
            "before_pipe",
            {
                "function": getattr(functions[0], "__name__", type(functions[0]).__name__),
                "context": ctx.to_dict(),
            },
        )

        current = propagation or self._new_propagation(pipeline_id, ctx.trace_id)

        current = self._publish(
            "RuntimePipelineStarted",
            EventType.START,
            Category.PIPELINE,
            {
                "pipeline_id": pipeline_id,
                "function_count": len(functions),
                "trace_id": ctx.trace_id,
            },
            current,
        )

        result = value

        try:
            for fn in functions:
                result, current = self._run_with_propagation(
                    fn,
                    (result,),
                    {},
                    current,
                    context=ctx,
                )

            current = self._publish(
                "RuntimePipelineCompleted",
                EventType.COMPLETE,
                Category.PIPELINE,
                {
                    "pipeline_id": pipeline_id,
                    "result": str(result),
                    "trace_id": ctx.trace_id,
                },
                current,
            )
            return result
        except _ExecutionFailureError as failure:
            current = failure.propagation
            self._publish(
                "RuntimePipelineFailed",
                EventType.FAILURE,
                Category.PIPELINE,
                {
                    "pipeline_id": pipeline_id,
                    "error": str(failure.exception),
                    "trace_id": ctx.trace_id,
                },
                current,
            )
            raise failure.exception from failure.exception.__cause__
        except SH3Exception as exc:
            self._publish(
                "RuntimePipelineFailed",
                EventType.FAILURE,
                Category.PIPELINE,
                {
                    "pipeline_id": pipeline_id,
                    "error": str(exc),
                    "trace_id": ctx.trace_id,
                },
                current,
            )
            raise
        except Exception as exc:
            wrapped = exc if isinstance(exc, RuntimeException) else RuntimeException(str(exc))
            self._publish(
                "RuntimePipelineFailed",
                EventType.FAILURE,
                Category.PIPELINE,
                {
                    "pipeline_id": pipeline_id,
                    "error": str(wrapped),
                    "trace_id": ctx.trace_id,
                },
                current,
            )
            if wrapped is exc:
                raise
            raise wrapped from exc


    def set_state(self, key: str, value: Any) -> None:
        if not key or not key.strip():
            raise ValueError("key must not be empty")
        with self._lock:
            self._state[key] = value


    def get_state(self, key: str, default: Any = None) -> Any:
        if not key or not key.strip():
            raise ValueError("key must not be empty")
        with self._lock:
            return self._state.get(key, default)


    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "state": dict(self._state),
                "context": self.context.to_dict(),
                "hooks": sorted(self.hooks),
            }
