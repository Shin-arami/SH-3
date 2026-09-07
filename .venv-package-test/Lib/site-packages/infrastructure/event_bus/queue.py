"""
SH-3 Complete Edition v2.0
Infrastructure Layer
Events Subsystem

queue.py

Thread-safe deterministic event queue primitives.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Condition, RLock
from typing import Final

from ..events.model import Event

__all__ = [
    "EventQueue",
    "QueueItem",
    "QueueSnapshot",
]


@dataclass(frozen=True, slots=True)
class QueueItem:
    sequence: int
    event: Event

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        if not isinstance(self.event, Event):
            raise TypeError("event must be Event")


@dataclass(frozen=True, slots=True)
class QueueSnapshot:
    name: str
    size: int
    capacity: int | None
    published: int
    consumed: int
    rejected: int
    sequence: int

    @property
    def full(self) -> bool:
        return self.capacity is not None and self.size >= self.capacity

    @property
    def empty(self) -> bool:
        return self.size == 0


class EventQueue:
    """Bounded or unbounded thread-safe FIFO event queue."""

    _UNBOUNDED: Final[int | None] = None

    def __init__(
        self,
        name: str,
        *,
        capacity: int | None = None,
    ) -> None:
        if not name:
            raise ValueError("queue name must not be empty")

        if capacity is not None and capacity <= 0:
            raise ValueError("capacity must be positive")

        self._name = name
        self._capacity = capacity
        self._items: deque[QueueItem] = deque()
        self._sequence = 0
        self._published = 0
        self._consumed = 0
        self._rejected = 0
        self._closed = False
        self._lock = RLock()
        self._condition = Condition(self._lock)

    @property
    def name(self) -> str:
        return self._name

    @property
    def capacity(self) -> int | None:
        return self._capacity

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    def put(
        self,
        event: Event,
    ) -> QueueItem:
        if not isinstance(event, Event):
            raise TypeError("event must be Event")

        with self._condition:
            self._ensure_open()

            if self._capacity is not None and len(self._items) >= self._capacity:
                self._rejected += 1
                raise OverflowError(f"queue is full: {self._name}")

            item = QueueItem(
                sequence=self._sequence,
                event=event,
            )

            self._sequence += 1
            self._items.append(item)
            self._published += 1
            self._condition.notify()

            return item

    def put_many(
        self,
        events: tuple[Event, ...],
    ) -> tuple[QueueItem, ...]:
        if not isinstance(events, tuple):
            raise TypeError("events must be tuple")

        with self._condition:
            self._ensure_open()

            if self._capacity is not None and len(self._items) + len(events) > self._capacity:
                self._rejected += len(events)
                raise OverflowError(f"queue capacity exceeded: {self._name}")

            items: list[QueueItem] = []

            for event in events:
                if not isinstance(event, Event):
                    raise TypeError("all events must be Event")

                item = QueueItem(
                    sequence=self._sequence,
                    event=event,
                )

                self._sequence += 1
                self._items.append(item)
                self._published += 1
                items.append(item)

            if items:
                self._condition.notify_all()

            return tuple(items)

    def get(
        self,
    ) -> QueueItem:
        with self._condition:
            if not self._items:
                raise IndexError(f"queue is empty: {self._name}")

            item = self._items.popleft()
            self._consumed += 1
            return item

    def get_nowait(self) -> QueueItem:
        return self.get()

    def peek(self) -> QueueItem:
        with self._lock:
            if not self._items:
                raise IndexError(f"queue is empty: {self._name}")

            return self._items[0]

    def drain(self) -> tuple[QueueItem, ...]:
        with self._condition:
            if not self._items:
                return ()

            items = tuple(self._items)
            self._items.clear()
            self._consumed += len(items)
            return items

    def wait_get(
        self,
        timeout: float | None = None,
    ) -> QueueItem | None:
        with self._condition:
            if not self._items and not self._closed:
                available = self._condition.wait(timeout)

                if not available and not self._items:
                    return None

            if not self._items:
                return None

            item = self._items.popleft()
            self._consumed += 1
            return item

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()

    def clear(self) -> tuple[QueueItem, ...]:
        with self._condition:
            items = tuple(self._items)
            self._items.clear()
            self._consumed += len(items)
            return items

    def size(self) -> int:
        with self._lock:
            return len(self._items)

    def empty(self) -> bool:
        with self._lock:
            return not self._items

    def full(self) -> bool:
        with self._lock:
            return self._capacity is not None and len(self._items) >= self._capacity

    def snapshot(self) -> QueueSnapshot:
        with self._lock:
            return QueueSnapshot(
                name=self._name,
                size=len(self._items),
                capacity=self._capacity,
                published=self._published,
                consumed=self._consumed,
                rejected=self._rejected,
                sequence=self._sequence,
            )

    def __len__(self) -> int:
        return self.size()

    def __bool__(self) -> bool:
        return not self.empty()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError(f"queue is closed: {self._name}")


class EventQueueSet:
    """Named collection of independent event queues."""

    def __init__(self) -> None:
        self._queues: dict[str, EventQueue] = {}
        self._lock = RLock()

    def create(
        self,
        name: str,
        *,
        capacity: int | None = None,
        replace: bool = False,
    ) -> EventQueue:
        with self._lock:
            if name in self._queues and not replace:
                raise ValueError(f"queue already exists: {name}")

            queue = EventQueue(
                name,
                capacity=capacity,
            )
            self._queues[name] = queue
            return queue

    def get(self, name: str) -> EventQueue:
        with self._lock:
            try:
                return self._queues[name]
            except KeyError as exc:
                raise KeyError(f"queue not found: {name}") from exc

    def remove(self, name: str) -> EventQueue:
        with self._lock:
            try:
                return self._queues.pop(name)
            except KeyError as exc:
                raise KeyError(f"queue not found: {name}") from exc

    def contains(self, name: str) -> bool:
        with self._lock:
            return name in self._queues

    def names(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._queues))

    def count(self) -> int:
        with self._lock:
            return len(self._queues)

    def clear(self) -> None:
        with self._lock:
            self._queues.clear()
