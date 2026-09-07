from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from foundation.utils.hash import short_id
from foundation.utils.logging import info
from foundation.utils.time import iso


class MemoryItem:
    """Single atomic memory unit."""

    def __init__(
        self,
        key: str,
        value: Any,
        tags: list[str] | None = None,
    ) -> None:
        self.key = key
        self.value = value
        self.tags = list(tags) if tags is not None else []
        self.timestamp = iso(datetime.now(UTC))
        self.trace_id = short_id(key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "tags": self.tags,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
        }


class MemoryCore:
    """SH-3 deterministic memory system."""

    def __init__(self) -> None:
        self._store: dict[str, MemoryItem] = {}
        self._timeline: list[str] = []

    def write(
        self,
        key: str,
        value: Any,
        tags: list[str] | None = None,
    ) -> str:
        mem = MemoryItem(key, value, tags)
        self._store[key] = mem
        self._timeline.append(key)
        info("Memory written", mem.to_dict())
        return key

    def read(self, key: str, default: Any = None) -> Any:
        item = self._store.get(key)
        return item.value if item is not None else default

    def update(self, key: str, value: Any) -> None:
        if key not in self._store:
            self.write(key, value)
        else:
            self._store[key].value = value
        info("Memory updated", {"key": key})

    def search_by_tag(self, tag: str) -> list[dict[str, Any]]:
        results = [
            item.to_dict()
            for item in self._store.values()
            if tag in item.tags
        ]
        info("Memory search by tag", {"tag": tag, "count": len(results)})
        return results

    def timeline(self, limit: int | None = None) -> list[dict[str, Any]]:
        if limit is not None:
            if isinstance(limit, bool) or not isinstance(limit, int):
                raise TypeError("limit must be int or None")
            if limit < 0:
                raise ValueError("limit must be >= 0")

        keys = (
            self._timeline
            if limit is None
            else self._timeline[-limit:]
            if limit
            else []
        )
        return [
            self._store[key].to_dict()
            for key in keys
            if key in self._store
        ]

    def compress(self, group_size: int = 5) -> list[dict[str, Any]]:
        """Deterministic compression of memory timeline."""
        if isinstance(group_size, bool) or not isinstance(group_size, int):
            raise TypeError("group_size must be int")
        if group_size < 1:
            raise ValueError("group_size must be >= 1")

        compressed: list[dict[str, Any]] = []

        for i in range(0, len(self._timeline), group_size):
            chunk_keys = self._timeline[i : i + group_size]
            combined: dict[str, Any] = {
                "group_id": short_id("".join(chunk_keys)),
                "items": [
                    self._store[key].to_dict()
                    for key in chunk_keys
                    if key in self._store
                ],
                "size": len(chunk_keys),
            }
            compressed.append(combined)

        info("Memory compressed", {"groups": len(compressed)})
        return compressed

    def snapshot(self) -> dict[str, Any]:
        return {
            "size": len(self._store),
            "timeline_length": len(self._timeline),
            "keys": list(self._store.keys()),
        }

    def clear(self) -> None:
        self._store.clear()
        self._timeline.clear()
        info("Memory cleared", {})
