from __future__ import annotations

from collections.abc import Callable
from typing import Any

from foundation.utils.hash import short_id
from foundation.utils.logging import info


class PolicyRule:
    """Deterministic decision rule unit."""

    def __init__(
        self,
        name: str,
        weight: float = 1.0,
        condition: Callable[[Any], bool] | None = None,
        score_fn: Callable[[Any], float] | None = None,
    ) -> None:
        self.name = name
        self.weight = weight
        self.condition = condition
        self.score_fn = score_fn
        self.trace_id = short_id(name)

    def evaluate(self, context: Any) -> float:
        if self.condition and not self.condition(context):
            return 0.0

        base_score = self.score_fn(context) if self.score_fn else 1.0
        return base_score * self.weight

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "weight": self.weight,
            "trace_id": self.trace_id,
        }


class PolicyEngine:
    """SH-3 deterministic decision policy system."""

    def __init__(self) -> None:
        self.rules: list[PolicyRule] = []

    def add_rule(self, rule: PolicyRule) -> None:
        self.rules.append(rule)
        info("Policy rule added", rule.to_dict())

    def remove_rule(self, name: str) -> None:
        self.rules = [r for r in self.rules if r.name != name]
        info("Policy rule removed", {"name": name})

    def clear(self) -> None:
        self.rules.clear()
        info("Policy rules cleared")

    def evaluate(self, context: Any) -> dict[str, float]:
        scores: dict[str, float] = {}
        for rule in self.rules:
            scores[rule.name] = rule.evaluate(context)
        info("Policy evaluation completed", scores)
        return scores

    def decide(self, context: Any) -> str | None:
        scores = self.evaluate(context)
        if not scores:
            return None
        best = max(scores.items(), key=lambda x: x[1])[0]
        info("Policy decision made", {"choice": best})
        return best

    def run(self, context: Any) -> dict[str, Any]:
        scores = self.evaluate(context)
        decision = self.decide(context)
        return {
            "context": str(context),
            "scores": scores,
            "decision": decision,
        }


def default_policy() -> PolicyEngine:
    engine = PolicyEngine()

    engine.add_rule(
        PolicyRule(
            name="length_preference",
            weight=1.0,
            score_fn=lambda x: len(str(x)) % 10 / 10.0,
        )
    )

    engine.add_rule(
        PolicyRule(
            name="non_empty_bias",
            weight=1.2,
            condition=lambda x: x is not None and str(x) != "",
            score_fn=lambda x: 1.0,
        )
    )

    engine.add_rule(
        PolicyRule(
            name="shortness_bias",
            weight=0.8,
            score_fn=lambda x: 1.0 / (len(str(x)) + 1),
        )
    )

    return engine
