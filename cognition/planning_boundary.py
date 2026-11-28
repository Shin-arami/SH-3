from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from threading import RLock
from typing import Any, Protocol

from cognition.contracts import CognitiveContext, CognitiveGoal, CognitivePlan
from cognition.planner import Planner

__all__ = ["CognitivePlanningBoundary", "PlanningBackend"]


class PlanningBackend(Protocol):
    def build_plan(self, goal: str) -> dict[str, Any]: ...


class CognitivePlanningBoundary:
    """Typed boundary between cognitive goal contracts and planning backends."""

    __slots__ = ("_backend", "_lock")

    def __init__(self, backend: PlanningBackend | None = None) -> None:
        self._lock = RLock()
        self._backend = backend or Planner()

    @property
    def backend(self) -> PlanningBackend:
        with self._lock:
            return self._backend

    def build_plan(
        self,
        goal: CognitiveGoal | str,
        *,
        context: CognitiveContext | None = None,
        created_at: datetime | None = None,
    ) -> CognitivePlan:
        resolved_goal = goal if isinstance(goal, CognitiveGoal) else CognitiveGoal.create(goal, created_at=created_at)
        if context is not None and context.goal_id != resolved_goal.goal_id:
            raise ValueError("context goal_id must match goal goal_id")
        with self._lock:
            legacy_plan = self._backend.build_plan(resolved_goal.intent)
        if not isinstance(legacy_plan, Mapping):
            raise TypeError("planning backend result must be a mapping")
        steps = self._steps(legacy_plan, resolved_goal.intent)
        plan_created_at = created_at
        if plan_created_at is None:
            raw_created_at = legacy_plan.get("created_at")
            if not isinstance(raw_created_at, str):
                raise ValueError("planning backend result must contain created_at")
            plan_created_at = datetime.fromisoformat(raw_created_at)
        metadata: dict[str, Any] = {"legacy_plan_trace_id": legacy_plan.get("trace_id", "")}
        if context is not None:
            metadata["planning_context_id"] = context.context_id
        return CognitivePlan.create(
            resolved_goal,
            steps,
            planning_type="execution",
            owner=resolved_goal.owner,
            version=resolved_goal.version,
            created_at=plan_created_at,
            correlation_id=context.correlation_id if context is not None else resolved_goal.correlation_id,
            causation_id=context.causation_id if context is not None else resolved_goal.causation_id,
            trace_id=context.trace_id if context is not None else resolved_goal.trace_id,
            tenant_id=context.tenant_id if context is not None else resolved_goal.tenant_id,
            metadata=metadata,
        )

    def plan(
        self,
        goal: CognitiveGoal | str,
        *,
        context: CognitiveContext | None = None,
        created_at: datetime | None = None,
    ) -> CognitivePlan:
        return self.build_plan(goal, context=context, created_at=created_at)

    @staticmethod
    def _steps(plan: Mapping[str, Any], intent: str) -> tuple[str, ...]:
        tree = plan.get("tree")
        if not isinstance(tree, Mapping):
            raise ValueError("planning backend result must contain a tree mapping")
        if tree.get("name") != intent:
            raise ValueError("planning backend tree name must match goal intent")
        children = tree.get("children", [])
        if not isinstance(children, list):
            raise ValueError("planning backend tree children must be a list")
        steps: list[str] = []
        for child in children:
            if not isinstance(child, Mapping):
                raise ValueError("planning backend tree children must be mappings")
            name = child.get("name")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("planning backend tree child name must be a non-empty string")
            steps.append(name)
        return tuple(steps)
