from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from threading import RLock
from typing import Any, Literal, Self

from foundation.utils.hash import short_id
from foundation.utils.logging import info

__all__ = ["ContextManager", "RuntimeContext"]


class RuntimeContext:
    __slots__ = ("children", "created_at", "name", "parent", "state", "trace_id")

    def __init__(
        self,
        name: str = "context",
        parent: RuntimeContext | None = None,
    ) -> None:
        self.name = name
        self.parent = parent
        self.state: dict[str, Any] = {}
        self.children: list[RuntimeContext] = []
        self.trace_id = short_id(name)
        self.created_at = datetime.now(UTC)
        if parent is not None:
            parent.children.append(self)

    def set(self, key: str, value: Any) -> None:
        self.state[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        if key in self.state:
            return self.state[key]
        if self.parent is not None:
            return self.parent.get(key, default)
        return default

    def update(self, data: Mapping[str, Any]) -> None:
        self.state.update(data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": dict(self.state),
            "trace_id": self.trace_id,
            "created_at": self.created_at.isoformat(),
            "parent": self.parent.name if self.parent is not None else None,
            "children": [child.name for child in self.children],
        }


class _ContextScope(AbstractContextManager[RuntimeContext]):
    __slots__ = ("_context", "_manager", "_name")

    def __init__(self, manager: ContextManager, name: str) -> None:
        self._manager = manager
        self._name = name
        self._context: RuntimeContext | None = None

    def __enter__(self) -> RuntimeContext:
        self._context = self._manager.push(self._name)
        return self._context

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> Literal[False]:
        self._manager.pop()
        return False


class ContextManager:
    __slots__ = ("_lock", "_stack")

    def __init__(self) -> None:
        self._stack: list[RuntimeContext] = []
        self._lock = RLock()

    def push(self, name: str = "ctx") -> RuntimeContext:
        with self._lock:
            parent = self._stack[-1] if self._stack else None
            context = RuntimeContext(name=name, parent=parent)
            self._stack.append(context)
            info("Context pushed", context.to_dict())
            return context

    def pop(self) -> RuntimeContext | None:
        with self._lock:
            if not self._stack:
                return None
            context = self._stack.pop()
            info("Context popped", context.to_dict())
            return context

    def current(self) -> RuntimeContext | None:
        with self._lock:
            return self._stack[-1] if self._stack else None

    def set(self, key: str, value: Any) -> None:
        context = self.current()
        if context is not None:
            context.set(key, value)

    def get(self, key: str, default: Any = None) -> Any:
        context = self.current()
        return context.get(key, default) if context is not None else default

    def update(self, data: Mapping[str, Any]) -> None:
        context = self.current()
        if context is not None:
            context.update(data)

    def scope(self, name: str = "ctx") -> _ContextScope:
        return _ContextScope(self, name)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            current = self._stack[-1] if self._stack else None
            return {
                "depth": len(self._stack),
                "current": current.to_dict() if current is not None else None,
                "stack": [context.to_dict() for context in self._stack],
            }

    def clear(self, *, idempotency_key: str | None = None) -> None:
        if idempotency_key is not None and (
            not isinstance(idempotency_key, str) or not idempotency_key.strip()
        ):
            raise ValueError("idempotency_key must not be empty")
        with self._lock:
            self._stack.clear()
        if idempotency_key is None:
            info("Context stack cleared")
        else:
            info("Context stack cleared", {"idempotency_key": idempotency_key})

    def __len__(self) -> int:
        with self._lock:
            return len(self._stack)

    def __iter__(self) -> Iterator[RuntimeContext]:
        with self._lock:
            return iter(tuple(self._stack))

    def __enter__(self) -> Self:
        self.push("scope")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> Literal[False]:
        self.pop()
        return False
