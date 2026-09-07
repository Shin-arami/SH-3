from __future__ import annotations

from typing import Any

from cognition.memory import MemoryCore
from cognition.planner import Planner
from cognition.policy import PolicyEngine
from foundation.utils.hash import short_id
from foundation.utils.logging import info
from kernel.core import SH3Kernel

__all__ = ["LearningLoop"]


class LearningLoop:
    __slots__ = (
        "kernel",
        "loop_id",
        "max_chunk_size",
        "max_weight",
        "memory",
        "min_chunk_size",
        "min_weight",
        "planner",
        "policy",
    )

    def __init__(
        self,
        kernel: SH3Kernel,
        *,
        min_weight: float = 0.1,
        max_weight: float = 5.0,
        min_chunk_size: int = 1,
        max_chunk_size: int = 8,
    ) -> None:
        if min_weight <= 0:
            raise ValueError("min_weight must be > 0")
        if max_weight < min_weight:
            raise ValueError("max_weight must be >= min_weight")
        if min_chunk_size < 1:
            raise ValueError("min_chunk_size must be >= 1")
        if max_chunk_size < min_chunk_size:
            raise ValueError("max_chunk_size must be >= min_chunk_size")

        self.kernel = kernel
        self.policy: PolicyEngine = kernel.policy
        self.planner: Planner = kernel.planner
        self.memory: MemoryCore = kernel.memory
        self.loop_id = short_id("learning-loop")
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

    def collect(self, execution_result: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(execution_result, dict):
            raise TypeError("execution_result must be dict")

        plan = execution_result.get("plan")
        if not isinstance(plan, dict):
            plan = {}

        tree = plan.get("tree")
        if not isinstance(tree, dict):
            tree = {}

        children = tree.get("children")
        plan_size = len(children) if isinstance(children, list) else 0

        decision = execution_result.get("decision")

        experience = {
            "goal": execution_result.get("goal"),
            "decision": decision,
            "plan_size": plan_size,
            "success": decision is not None,
        }

        info("Experience collected", experience)
        return experience

    def evaluate(self, experience: dict[str, Any]) -> float:
        if not isinstance(experience, dict):
            raise TypeError("experience must be dict")

        score = 0.0

        if bool(experience.get("success")):
            score += 0.6

        plan_size = experience.get("plan_size", 0)
        if isinstance(plan_size, bool) or not isinstance(plan_size, int):
            raise TypeError("experience plan_size must be int")
        if plan_size < 0:
            raise ValueError("experience plan_size must be >= 0")

        score += min(0.4, plan_size * 0.05)

        return round(score, 3)

    def update_policy(
        self,
        experience: dict[str, Any],
        score: float,
    ) -> None:
        if not 0.0 <= score <= 1.0:
            raise ValueError("score must be between 0.0 and 1.0")

        if score < 0.3:
            factor = 0.95
            action = "weakened"
        elif score > 0.7:
            factor = 1.02
            action = "reinforced"
        else:
            info("Policy unchanged", {"score": score})
            return

        for rule in self.policy.rules:
            rule.weight = min(
                self.max_weight,
                max(self.min_weight, rule.weight * factor),
            )

        info(
            "Policy updated",
            {
                "score": score,
                "factor": factor,
                "action": action,
                "rules": len(self.policy.rules),
            },
        )

    def tune_planner(
        self,
        experience: dict[str, Any],
        score: float,
    ) -> None:
        if not 0.0 <= score <= 1.0:
            raise ValueError("score must be between 0.0 and 1.0")

        current = self.planner.chunk_size

        if score < 0.3:
            target = max(self.min_chunk_size, current - 1)
            action = "finer"
        elif score > 0.8:
            target = min(self.max_chunk_size, current + 1)
            action = "coarser"
        else:
            target = current
            action = "unchanged"

        if target != current:
            self.planner.set_chunk_size(target)

        info(
            "Planner tuned",
            {
                "score": score,
                "previous_chunk_size": current,
                "chunk_size": target,
                "action": action,
            },
        )

    def store_experience(
        self,
        experience: dict[str, Any],
        score: float,
    ) -> str:
        if not isinstance(experience, dict):
            raise TypeError("experience must be dict")
        if not 0.0 <= score <= 1.0:
            raise ValueError("score must be between 0.0 and 1.0")

        key = short_id(str(experience))

        self.memory.write(
            key=key,
            value={
                "experience": experience,
                "score": score,
            },
            tags=["learning", "experience"],
        )

        return key

    def run(self, execution_result: dict[str, Any]) -> dict[str, Any]:
        experience = self.collect(execution_result)
        score = self.evaluate(experience)
        self.update_policy(experience, score)
        self.tune_planner(experience, score)
        memory_key = self.store_experience(experience, score)

        result = {
            "loop_id": self.loop_id,
            "experience": experience,
            "score": score,
            "memory_key": memory_key,
        }

        info("Learning loop completed", result)
        return result
