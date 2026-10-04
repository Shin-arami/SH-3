from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from cognition.contracts import (
    CognitiveContext,
    CognitiveDecision,
    CognitiveGoal,
    CognitiveLifecycleState,
    CognitivePlan,
    CognitiveResult,
    CognitiveResultStatus,
)
from cognition.contracts import CognitiveState as CognitiveStateContract
from cognition.planning_boundary import CognitivePlanningBoundary
from foundation.utils.hash import short_id
from foundation.utils.logging import info
from foundation.utils.time import iso
from runtime.context_manager import ContextManager

__all__ = ["CognitionCore", "CognitiveState"]


class CognitiveState:
    """Legacy mutable cognition state compatibility model."""

    def __init__(self, goal: str):
        self.goal = goal
        self.steps: list[str] = []
        self.assumptions: list[str] = []
        self.results: dict[str, Any] = {}
        self.trace_id = short_id(goal)
        self.created_at = iso(datetime.now(UTC))

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


class CognitionCore:
    """SH-3 cognition engine with a typed contract path and legacy compatibility."""

    def __init__(
        self,
        context_manager: ContextManager | None = None,
        planning_boundary: CognitivePlanningBoundary | None = None,
    ):
        self.cm = context_manager or ContextManager()
        self.planning_boundary = planning_boundary or CognitivePlanningBoundary()

    def create_state(self, goal: str) -> CognitiveState:
        state = CognitiveState(goal)
        self.cm.set("goal", goal)
        self.cm.set("cognitive_state", state.to_dict())
        info("Cognitive state created", state.to_dict())
        return state

    def decompose(self, goal: str) -> list[str]:
        parts = goal.split(" ")
        steps = []
        buffer = []
        for part in parts:
            buffer.append(part)
            if len(buffer) >= 3:
                steps.append(" ".join(buffer))
                buffer = []
        if buffer:
            steps.append(" ".join(buffer))
        info("Goal decomposed", {"goal": goal, "steps": steps})
        return steps

    def plan(self, goal: str) -> dict[str, Any]:
        state = self.create_state(goal)
        steps = self.decompose(goal)
        for step in steps:
            state.add_step(step)
        plan = {"goal": goal, "steps": steps, "trace_id": state.trace_id}
        self.cm.set("plan", plan)
        info("Plan generated", plan)
        return plan

    def evaluate(self, items: list[str]) -> dict[str, float]:
        scores = {}
        for item in items:
            scores[item] = len(item) % 10 / 10.0
        info("Evaluation completed", scores)
        return scores

    def decide(self, options: list[str]) -> str | None:
        scores = self.evaluate(options)
        if not scores:
            return None
        best = max(scores.items(), key=lambda item: item[1])[0]
        self.cm.set("decision", best)
        info("Decision made", {"choice": best})
        return best

    def run(
        self,
        goal: str,
        policy: Callable[[list[str]], str | None] | None = None,
    ) -> dict[str, Any]:
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
            result = {"goal": goal, "plan": plan, "decision": decision}
            self.cm.set("result", result)
            return result
        finally:
            self.cm.pop()

    def create_goal(
        self,
        intent: str,
        *,
        owner: str = "cognition",
        goal_type: str = "goal",
        version: str = "1.0.0",
        created_at: datetime | None = None,
        lifecycle_state: CognitiveLifecycleState = CognitiveLifecycleState.CREATED,
        success_criteria: tuple[str, ...] = (),
        constraints: Mapping[str, Any] | None = None,
        priority: float = 0.0,
        time_horizon: str | None = None,
        goal_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        tenant_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> CognitiveGoal:
        return CognitiveGoal.create(
            intent,
            owner=owner,
            goal_type=goal_type,
            version=version,
            created_at=created_at,
            lifecycle_state=lifecycle_state,
            success_criteria=success_criteria,
            constraints=constraints,
            priority=priority,
            time_horizon=time_horizon,
            goal_id=goal_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            trace_id=trace_id,
            tenant_id=tenant_id,
            metadata=metadata,
        )

    def create_context(
        self,
        goal: CognitiveGoal,
        *,
        values: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        causation_id: str | None = None,
    ) -> CognitiveContext:
        if not isinstance(goal, CognitiveGoal):
            raise TypeError("goal must be CognitiveGoal")
        return CognitiveContext.create(
            goal.goal_id,
            correlation_id=goal.correlation_id,
            causation_id=causation_id,
            trace_id=goal.trace_id,
            tenant_id=goal.tenant_id,
            values=values,
            metadata=metadata,
        )

    def plan_contract(
        self,
        goal: CognitiveGoal | str,
        *,
        context: CognitiveContext | None = None,
        created_at: datetime | None = None,
    ) -> CognitivePlan:
        return self.planning_boundary.build_plan(goal, context=context, created_at=created_at)

    def run_contract(
        self,
        goal: CognitiveGoal | str,
        policy: Callable[[list[str]], str | None] | None = None,
        *,
        context: CognitiveContext | None = None,
        created_at: datetime | None = None,
    ) -> CognitiveResult:
        resolved_goal = (
            goal
            if isinstance(goal, CognitiveGoal)
            else self.create_goal(goal, created_at=created_at)
        )
        resolved_context = context or self.create_context(resolved_goal)
        timestamp = created_at or resolved_goal.created_at
        try:
            plan = self.plan_contract(resolved_goal, context=resolved_context, created_at=timestamp)
            options = list(plan.steps)
            decision_value = self.decide(options) if policy is None else policy(options)
            if decision_value is not None and decision_value not in options:
                raise ValueError("policy decision must be one of the plan options")
            decision = CognitiveDecision.create(
                resolved_goal,
                plan.steps,
                selected_option=decision_value,
                lifecycle_state=CognitiveLifecycleState.COMPLETED,
                created_at=timestamp,
                causation_id=plan.plan_id,
                correlation_id=plan.correlation_id,
                trace_id=plan.trace_id,
                tenant_id=plan.tenant_id,
                metadata={"plan_id": plan.plan_id},
            )
            state = CognitiveStateContract.from_goal(
                resolved_goal,
                context=resolved_context,
                steps=plan.steps,
                results={"decision": decision_value},
                lifecycle_state=CognitiveLifecycleState.COMPLETED,
                created_at=timestamp,
                updated_at=timestamp,
                metadata={"plan_id": plan.plan_id, "decision_id": decision.decision_id},
            )
            return CognitiveResult.create(
                resolved_goal,
                status=CognitiveResultStatus.SUCCESS,
                created_at=timestamp,
                output={
                    "goal": resolved_goal.to_dict(),
                    "plan": plan.to_dict(),
                    "decision": decision.to_dict(),
                    "state": state.to_dict(),
                },
                causation_id=decision.decision_id,
                correlation_id=decision.correlation_id,
                trace_id=decision.trace_id,
                tenant_id=decision.tenant_id,
                metadata={"context_id": resolved_context.context_id},
            )
        except Exception as exc:
            return CognitiveResult.create(
                resolved_goal,
                status=CognitiveResultStatus.FAILURE,
                created_at=timestamp,
                error_type=type(exc).__name__,
                error_message=str(exc),
                correlation_id=resolved_context.correlation_id,
                causation_id=resolved_context.causation_id,
                trace_id=resolved_context.trace_id,
                tenant_id=resolved_context.tenant_id,
                metadata={"context_id": resolved_context.context_id},
            )
