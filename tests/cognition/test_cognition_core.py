from __future__ import annotations

import pytest

from cognition.core import CognitionCore


def test_run_uses_the_supplied_policy_decision() -> None:
    cognition = CognitionCore()

    result = cognition.run(
        "prepare release notes today",
        policy=lambda options: options[-1],
    )

    assert result["decision"] == "today"


def test_run_rejects_policy_decisions_outside_the_plan() -> None:
    cognition = CognitionCore()

    with pytest.raises(ValueError, match="plan options"):
        cognition.run("prepare release notes", policy=lambda _: "unknown")
