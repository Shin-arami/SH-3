from __future__ import annotations

import pytest

from cognition.planner import Planner


def test_chunk_size_controls_goal_decomposition() -> None:
    planner = Planner(chunk_size=3)
    plan = planner.build_plan("one two three four")

    children = plan["tree"]["children"]
    assert [child["name"] for child in children] == ["one two three", "four"]
    assert [child["children"][0]["name"] for child in children] == [
        "one two three",
        "four",
    ]


@pytest.mark.parametrize("chunk_size", [0, -1])
def test_chunk_size_must_be_positive(chunk_size: int) -> None:
    with pytest.raises(ValueError, match="chunk_size"):
        Planner(chunk_size)
