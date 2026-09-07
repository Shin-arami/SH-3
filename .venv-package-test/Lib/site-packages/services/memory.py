from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from threading import RLock
from types import MappingProxyType
from typing import Any

from foundation.utils.exceptions import SH3Exception

from .base import Service

__all__ = ["MemoryEntry", "MemoryException", "MemoryService"]


class MemoryException(SH3Exception):
    """Memory service failure."""


@dataclass(frozen=True, slots=True)
class MemoryEntry:
    key: str
    value: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.key or not self.key.strip():
            raise ValueError("key must not be empty")
        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(dict(self.metadata)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "metadata": dict(self.metadata),
        }


class MemoryService(Service):
    __slots__ = ("_entries", "_memory_lock")

    def __init__(self, name: str = "memory") -> None:
        super().__init__(name)
        self._entries: dict[str, MemoryEntry] = {}
        self._memory_lock = RLock()

    def _on_start(self) -> None:
        return None

    def _on_suspend(self) -> None:
        return None

    def _on_resume(self) -> None:
        return None

    def _on_terminate(self) -> None:
        with self._memory_lock:
            self._entries.clear()

    def store(
        self,
        key: str,
        value: Any,
        metadata: Mapping[str, Any] | None = None,
    ) -> MemoryEntry:
        if not self.active:
            raise MemoryException(f"Memory service '{self.name}' is not active")
        entry = MemoryEntry(
            key=key,
            value=value,
            metadata=metadata or {},
        )
        with self._memory_lock:
            self._entries[key] = entry
        return entry

    def get(self, key: str) -> MemoryEntry | None:
        if not key or not key.strip():
            raise ValueError("key must not be empty")
        with self._memory_lock:
            return self._entries.get(key)

    def require(self, key: str) -> MemoryEntry:
        entry = self.get(key)
        if entry is None:
            raise MemoryException(f"Memory entry not found: {key}")
        return entry

    def remove(self, key: str) -> MemoryEntry | None:
        if not key or not key.strip():
            raise ValueError("key must not be empty")
        with self._memory_lock:
            return self._entries.pop(key, None)

    def contains(self, key: str) -> bool:
        if not key or not key.strip():
            raise ValueError("key must not be empty")
        with self._memory_lock:
            return key in self._entries

    def clear(self) -> None:
        with self._memory_lock:
            self._entries.clear()

    def entries(self) -> tuple[MemoryEntry, ...]:
        with self._memory_lock:
            return tuple(self._entries.values())

    def keys(self) -> tuple[str, ...]:
        with self._memory_lock:
            return tuple(self._entries)

    def count(self) -> int:
        with self._memory_lock:
            return len(self._entries)

    def snapshot(self) -> dict[str, Any]:
        with self._memory_lock:
            entries = tuple(self._entries.values())
        snapshot = super().snapshot()
        snapshot.update(
            {
                "entry_count": len(entries),
                "entries": [entry.to_dict() for entry in entries],
            }
        )
        return snapshot
