from __future__ import annotations

from typing import Any, cast

import pytest

from services.memory import MemoryEntry, MemoryException, MemoryService


def test_memory_defaults() -> None:
    memory = MemoryService()
    assert memory.name == "memory"
    assert memory.count() == 0
    assert memory.entries() == ()


def test_memory_entry_is_immutable() -> None:
    entry = MemoryEntry("key", "value", {"source": "test"})
    with pytest.raises((AttributeError, TypeError)):
        entry.key = "other"  # type: ignore[misc]
    with pytest.raises(TypeError):
        cast(Any, entry.metadata)["x"] = 1


def test_store_requires_active_service() -> None:
    memory = MemoryService()
    with pytest.raises(MemoryException):
        memory.store("key", "value")


def test_store_and_get() -> None:
    memory = MemoryService()
    memory.start()

    entry = memory.store("key", "value", {"source": "test"})

    assert memory.get("key") is entry
    assert entry.value == "value"
    assert entry.metadata["source"] == "test"
    assert memory.count() == 1


def test_store_replaces_existing_entry() -> None:
    memory = MemoryService()
    memory.start()

    first = memory.store("key", "first")
    second = memory.store("key", "second")

    assert memory.get("key") is second
    assert memory.get("key") is not first
    assert memory.count() == 1


def test_require_returns_entry() -> None:
    memory = MemoryService()
    memory.start()
    memory.store("key", "value")

    assert memory.require("key").value == "value"


def test_require_missing_entry_raises() -> None:
    memory = MemoryService()
    memory.start()

    with pytest.raises(MemoryException):
        memory.require("missing")


def test_contains_and_remove() -> None:
    memory = MemoryService()
    memory.start()
    entry = memory.store("key", "value")

    assert memory.contains("key") is True
    assert memory.remove("key") is entry
    assert memory.contains("key") is False
    assert memory.count() == 0


def test_clear() -> None:
    memory = MemoryService()
    memory.start()
    memory.store("a", 1)
    memory.store("b", 2)

    memory.clear()

    assert memory.count() == 0
    assert memory.entries() == ()


def test_snapshot() -> None:
    memory = MemoryService()
    memory.start()
    memory.store("key", "value", {"source": "test"})

    snapshot = memory.snapshot()

    assert snapshot["name"] == "memory"
    assert snapshot["state"] == "ACTIVE"
    assert snapshot["entry_count"] == 1
    assert snapshot["entries"][0]["key"] == "key"


def test_terminate_clears_memory() -> None:
    memory = MemoryService()
    memory.start()
    memory.store("key", "value")

    memory.terminate()

    assert memory.count() == 0
