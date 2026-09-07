"""
SH-3 Complete Edition v2.0
Infrastructure Layer
Events Subsystem

dead_letter.py

Deterministic dead-letter event management.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from threading import RLock
from typing import Final

from ..events.model import Event

__all__ = [
    "DeadLetterEntry",
    "DeadLetterQueue",
    "DeadLetterReason",
    "DeadLetterSnapshot",
]


class DeadLetterReason:
    """Canonical dead-letter reasons."""

    DELIVERY_FAILED: Final[str] = "delivery_failed"
    RETRY_EXHAUSTED: Final[str] = "retry_exhausted"
    INVALID_EVENT: Final[str] = "invalid_event"
    ROUTING_FAILED: Final[str] = "routing_failed"
    QUEUE_REJECTED: Final[str] = "queue_rejected"
    UNKNOWN: Final[str] = "unknown"


@dataclass(frozen=True, slots=True)
class DeadLetterEntry:
    """Immutable dead-letter record."""

    sequence: int
    event: Event
    reason: str
    error: str | None
    subscriber_id: str | None
    created_at: str

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        if not isinstance(self.event, Event):
            raise TypeError("event must be Event")
        if not self.reason:
            raise ValueError("reason must not be empty")
        if self.subscriber_id is not None and not self.subscriber_id:
            raise ValueError("subscriber_id must not be empty")
        if self.error is not None and not isinstance(
            self.error,
            str,
        ):
            raise TypeError("error must be str or None")
        if not self.created_at:
            raise ValueError("created_at must not be empty")


@dataclass(frozen=True, slots=True)
class DeadLetterSnapshot:
    """Immutable dead-letter queue metrics."""

    name: str
    size: int
    capacity: int | None
    stored: int
    rejected: int
    released: int
    sequence: int

    @property
    def empty(self) -> bool:
        return self.size == 0

    @property
    def full(self) -> bool:
        return self.capacity is not None and self.size >= self.capacity


class DeadLetterQueue:
    """Thread-safe deterministic dead-letter queue."""

    _UTC: Final[timezone] = UTC

    def __init__(
        self,
        name: str = "dead_letter",
        *,
        capacity: int | None = None,
    ) -> None:
        if not name:
            raise ValueError("queue name must not be empty")

        if capacity is not None and capacity <= 0:
            raise ValueError("capacity must be positive")

        self._name = name
        self._capacity = capacity
        self._entries: list[DeadLetterEntry] = []
        self._sequence = 0
        self._stored = 0
        self._rejected = 0
        self._released = 0
        self._lock = RLock()

    @property
    def name(self) -> str:
        return self._name

    @property
    def capacity(self) -> int | None:
        return self._capacity

    def put(
        self,
        event: Event,
        *,
        reason: str = DeadLetterReason.UNKNOWN,
        error: str | None = None,
        subscriber_id: str | None = None,
    ) -> DeadLetterEntry:
        if not isinstance(event, Event):
            raise TypeError("event must be Event")

        if not reason:
            raise ValueError("reason must not be empty")

        with self._lock:
            if self._capacity is not None and len(self._entries) >= self._capacity:
                self._rejected += 1
                raise OverflowError(f"dead-letter queue is full: {self._name}")

            entry = DeadLetterEntry(
                sequence=self._sequence,
                event=event,
                reason=reason,
                error=error,
                subscriber_id=subscriber_id,
                created_at=self._timestamp(),
            )

            self._sequence += 1
            self._entries.append(entry)
            self._stored += 1

            return entry

    def put_entry(
        self,
        entry: DeadLetterEntry,
    ) -> DeadLetterEntry:
        if not isinstance(entry, DeadLetterEntry):
            raise TypeError("entry must be DeadLetterEntry")

        with self._lock:
            if self._capacity is not None and len(self._entries) >= self._capacity:
                self._rejected += 1
                raise OverflowError(f"dead-letter queue is full: {self._name}")

            self._entries.append(entry)
            self._stored += 1
            self._sequence = max(
                self._sequence,
                entry.sequence + 1,
            )

            return entry

    def get(self) -> DeadLetterEntry:
        with self._lock:
            if not self._entries:
                raise IndexError(f"dead-letter queue is empty: {self._name}")

            entry = self._entries.pop(0)
            self._released += 1
            return entry

    def get_nowait(self) -> DeadLetterEntry:
        return self.get()

    def peek(self) -> DeadLetterEntry:
        with self._lock:
            if not self._entries:
                raise IndexError(f"dead-letter queue is empty: {self._name}")

            return self._entries[0]

    def drain(self) -> tuple[DeadLetterEntry, ...]:
        with self._lock:
            if not self._entries:
                return ()

            entries = tuple(self._entries)
            self._entries.clear()
            self._released += len(entries)

            return entries

    def clear(self) -> tuple[DeadLetterEntry, ...]:
        return self.drain()

    def size(self) -> int:
        with self._lock:
            return len(self._entries)

    def empty(self) -> bool:
        with self._lock:
            return not self._entries

    def full(self) -> bool:
        with self._lock:
            return self._capacity is not None and len(self._entries) >= self._capacity

    def snapshot(self) -> DeadLetterSnapshot:
        with self._lock:
            return DeadLetterSnapshot(
                name=self._name,
                size=len(self._entries),
                capacity=self._capacity,
                stored=self._stored,
                rejected=self._rejected,
                released=self._released,
                sequence=self._sequence,
            )

    def entries(self) -> tuple[DeadLetterEntry, ...]:
        with self._lock:
            return tuple(self._entries)

    def find_by_event(
        self,
        event_id: str,
    ) -> tuple[DeadLetterEntry, ...]:
        if not event_id:
            raise ValueError("event_id must not be empty")

        with self._lock:
            return tuple(entry for entry in self._entries if entry.event.id == event_id)

    def find_by_reason(
        self,
        reason: str,
    ) -> tuple[DeadLetterEntry, ...]:
        if not reason:
            raise ValueError("reason must not be empty")

        with self._lock:
            return tuple(entry for entry in self._entries if entry.reason == reason)

    def count(self) -> int:
        return self.size()

    def stored(self) -> int:
        with self._lock:
            return self._stored

    def rejected(self) -> int:
        with self._lock:
            return self._rejected

    def released(self) -> int:
        with self._lock:
            return self._released

    def __len__(self) -> int:
        return self.size()

    def __bool__(self) -> bool:
        return not self.empty()

    @classmethod
    def _timestamp(cls) -> str:
        return datetime.now(cls._UTC).isoformat()
