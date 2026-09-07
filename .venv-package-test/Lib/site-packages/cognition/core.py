# cognition/core.py

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from foundation.utils.hash import short_id
from foundation.utils.logging import info
from foundation.utils.time import iso
from runtime.context_manager import ContextManager

# ----------------------------
# Cognitive State
# ----------------------------


class CognitiveState:
    """
    Represents working memory for cognition layer.
    """

    def __init__(self, goal: str):
        self.goal = goal
        self.steps: list[str] = []
        self.assumptions: list[str] = []
        self.results: dict[str, Any] = {}
        self.trace_id = short_id(goal)
        self.created_at = iso(__import__("datetime").datetime.utcnow())

    def add_step(self, step: str) -> None:
        self.steps.append(step)

    def add_assumption(self, assumption: str) -> None:
        self.assumptions.append(assumption)

    def set_result(self, key: str, value: Any) -> None:
        self.results[key] = value

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "steps": self.steps,
            "assumptions": self.assumptions,
            "results": self.results,
            "trace_id": self.trace_id,
            "created_at": self.created_at,
        }


# ----------------------------
# Cognitive Core Engine
# ----------------------------


class CognitionCore:
    """
    SH-3 reasoning / decision engine.
    """

    def __init__(self, context_manager: ContextManager | None = None):
        self.cm = context_manager or ContextManager()

    # ------------------------
    # Goal Initialization
    # ------------------------

    def create_state(self, goal: str) -> CognitiveState:
        state = CognitiveState(goal)
        self.cm.set("goal", goal)
        self.cm.set("cognitive_state", state.to_dict())

        info("Cognitive state created", state.to_dict())
        return state

    # ------------------------
    # Decomposition (reasoning step)
    # ------------------------

    def decompose(self, goal: str) -> list[str]:
        """
        Deterministic heuristic decomposition.
        (No AI, rule-based expansion)
        """
        parts = goal.split(" ")

        steps = []
        buffer = []

        for p in parts:
            buffer.append(p)
            if len(buffer) >= 3:
                steps.append(" ".join(buffer))
                buffer = []

        if buffer:
            steps.append(" ".join(buffer))

        info("Goal decomposed", {"goal": goal, "steps": steps})
        return steps

    # ------------------------
    # Planning
    # ------------------------

    def plan(self, goal: str) -> dict[str, Any]:
        state = self.create_state(goal)

        steps = self.decompose(goal)
        for s in steps:
            state.add_step(s)

        plan = {
            "goal": goal,
            "steps": steps,
            "trace_id": state.trace_id,
        }

        self.cm.set("plan", plan)

        info("Plan generated", plan)
        return plan

    # ------------------------
    # Evaluation (rule-based scoring)
    # ------------------------

    def evaluate(self, items: list[str]) -> dict[str, float]:
        scores = {}

        for item in items:
            score = len(item) % 10 / 10.0
            scores[item] = score

        info("Evaluation completed", scores)
        return scores

    # ------------------------
    # Decision making
    # ------------------------

    def decide(self, options: list[str]) -> str | None:
        scores = self.evaluate(options)

        if not scores:
            return None

        best = max(scores.items(), key=lambda x: x[1])[0]

        self.cm.set("decision", best)
        info("Decision made", {"choice": best})

        return best

    # ------------------------
    # Execution bridge
    # ------------------------

    def run(
        self,
        goal: str,
        policy: Callable[[list[str]], str | None] | None = None,
    ) -> dict[str, Any]:
        """
        Full cognition pipeline:
        goal → plan → evaluate → decide
        """

        self.cm.push("cognition")

        try:
            plan = self.plan(goal)

            options = plan["steps"]
            if policy is None:
                decision = self.decide(options)
            else:
                decision = policy(options)
                if decision is not None and decision not in options:
                    raise ValueError("policy decision must be one of the plan options")
                self.cm.set("decision", decision)
                info("Policy decision made", {"choice": decision})

            result = {
                "goal": goal,
                "plan": plan,
                "decision": decision,
            }

            self.cm.set("result", result)

            return result

        finally:
            self.cm.pop()
