from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from foundation.Enums.priority import Priority
from runtime.execution import ExecutionRequest

__all__ = ["RuntimeExecutionScheduler", "ScheduledExecution"]


@dataclass(frozen=True, slots=True)
class ScheduledExecution:
    request: ExecutionRequest
    sequence: int

    @property
    def execution_id(self) -> str:
        return self.request.execution_id

    @property
    def priority(self) -> Priority:
        return self.request.priority


class RuntimeExecutionScheduler:
    __slots__ = ("_items", "_lock", "_next_sequence")

    def __init__(self) -> None:
        self._lock = RLock()
        self._items: dict[str, ScheduledExecution] = {}
        self._next_sequence = 0

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._items)

    @property
    def empty(self) -> bool:
        with self._lock:
            return not self._items

    def enqueue(self, request: ExecutionRequest) -> ScheduledExecution:
        if not isinstance(request, ExecutionRequest):
            raise TypeError("request must be ExecutionRequest")
        with self._lock:
            if request.execution_id in self._items:
                raise ValueError(f"execution already scheduled: {request.execution_id}")
            item = ScheduledExecution(request=request, sequence=self._next_sequence)
            self._next_sequence += 1
            self._items[request.execution_id] = item
            return item

    def get(self, execution_id: str) -> ScheduledExecution | None:
        if not execution_id:
            raise ValueError("execution_id must not be empty")
        with self._lock:
            return self._items.get(execution_id)

    def contains(self, execution_id: str) -> bool:
        if not execution_id:
            raise ValueError("execution_id must not be empty")
        with self._lock:
            return execution_id in self._items

    def peek(self) -> ScheduledExecution | None:
        with self._lock:
            if not self._items:
                return None
            return min(self._items.values(), key=self._sort_key)

    def dequeue(self) -> ScheduledExecution | None:
        with self._lock:
            if not self._items:
                return None
            item = min(self._items.values(), key=self._sort_key)
            del self._items[item.execution_id]
            return item

    def remove(self, execution_id: str) -> ScheduledExecution | None:
        if not execution_id:
            raise ValueError("execution_id must not be empty")
        with self._lock:
            return self._items.pop(execution_id, None)

    def clear(self) -> tuple[ScheduledExecution, ...]:
        with self._lock:
            items = tuple(sorted(self._items.values(), key=self._sort_key))
            self._items.clear()
            return items

    def pending(self) -> tuple[ScheduledExecution, ...]:
        with self._lock:
            return tuple(sorted(self._items.values(), key=self._sort_key))

    @staticmethod
    def _priority_rank(priority: Priority) -> int:
        ranks = {
            Priority.CRITICAL: 0,
            Priority.HIGH: 1,
            Priority.NORMAL: 2,
            Priority.LOW: 3,
        }
        try:
            return ranks[priority]
        except KeyError as exc:
            raise ValueError(f"unsupported priority: {priority!r}") from exc

    @classmethod
    def _sort_key(cls, item: ScheduledExecution) -> tuple[int, int, str]:
        return (
            cls._priority_rank(item.priority),
            item.sequence,
            item.execution_id,
        )
