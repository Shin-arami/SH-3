from __future__ import annotations

from typing import Any, cast

import pytest

from cognition.memory import MemoryCore


def test_timeline_zero_returns_no_items() -> None:
    memory = MemoryCore()
    memory.write("first", {"value": 1})

    assert memory.timeline(0) == []


@pytest.mark.parametrize("limit", [-1, "1"])
def test_timeline_validates_limit(limit: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        MemoryCore().timeline(cast(Any, limit))


@pytest.mark.parametrize("group_size", [0, -1, "5"])
def test_compress_validates_group_size(group_size: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        MemoryCore().compress(cast(Any, group_size))
