from __future__ import annotations

import pytest

from cognition.policy import PolicyRule
from kernel import SH3Kernel
from kernel.learning_loop import LearningLoop


def test_run_collects_scores_and_stores_experience() -> None:
    kernel = SH3Kernel()
    kernel.add_policy(PolicyRule("always", score_fn=lambda _: 1.0))

    result = LearningLoop(kernel).run(kernel.execute("prepare release notes"))

    assert result["experience"] == {
        "goal": "prepare release notes",
        "decision": "always",
        "plan_size": 2,
        "success": True,
    }
    assert result["score"] == 0.7
    assert kernel.recall(result["memory_key"]) == {
        "experience": result["experience"],
        "score": 0.7,
    }


def test_low_score_weakens_policy_weights() -> None:
    kernel = SH3Kernel()
    rule = PolicyRule("always")
    kernel.add_policy(rule)

    result = LearningLoop(kernel).run({"goal": "", "plan": {"tree": {}}})

    assert result["score"] == 0.0
    assert rule.weight == pytest.approx(0.95)
    assert kernel.planner.chunk_size == 1


def test_high_score_uses_coarser_planner_decomposition() -> None:
    kernel = SH3Kernel()
    loop = LearningLoop(kernel)

    loop.tune_planner({}, 0.9)

    assert kernel.planner.chunk_size == 3
