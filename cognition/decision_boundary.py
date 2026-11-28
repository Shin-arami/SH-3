from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from threading import RLock
from typing import Protocol

from cognition.contracts import (
    CognitiveContext,
    CognitiveDecision,
    CognitiveGoal,
    CognitiveLifecycleState,
    CognitivePlan,
)
from cognition.policy_boundary import CognitivePolicyEvaluation

__all__ = ["CognitiveDecisionBoundary", "DecisionBackend"]


class DecisionBackend(Protocol):
    def decide(self, options: tuple[str, ...]) -> str | None: ...


class CognitiveDecisionBoundary:
    """Typed boundary between cognitive plans, policy evaluation, and decisions."""

    __slots__ = ("_backend", "_lock")

    def __init__(self, backend: DecisionBackend | Callable[[tuple[str, ...]], str | None] | None = None) -> None:
        self._lock = RLock()
        self._backend = backend or _DeterministicDecisionBackend()

    @property
    def backend(self) -> DecisionBackend | Callable[[tuple[str, ...]], str | None]:
        with self._lock:
            return self._backend

    def decide(
        self,
        goal: CognitiveGoal,
        plan: CognitivePlan,
        *,
        context: CognitiveContext | None = None,
        policy_evaluation: CognitivePolicyEvaluation | None = None,
        created_at: datetime | None = None,
        decision_type: str = "selection",
        rationale: str = "",
        utility: float | None = None,
        risk: float | None = None,
    ) -> CognitiveDecision:
        if not isinstance(goal, CognitiveGoal):
            raise TypeError("goal must be CognitiveGoal")
        if not isinstance(plan, CognitivePlan):
            raise TypeError("plan must be CognitivePlan")
        if plan.goal_id != goal.goal_id:
            raise ValueError("plan goal_id must match goal_id")
        if context is not None and context.goal_id != goal.goal_id:
            raise ValueError("context goal_id must match goal_id")
        if policy_evaluation is not None:
            self._validate_policy_chain(goal, plan, context, policy_evaluation)
        options = plan.steps
        with self._lock:
            backend = self._backend
            selected = backend(options) if callable(backend) else backend.decide(options)
        if selected is not None and selected not in options:
            raise ValueError("decision backend result must be one of plan options")
        timestamp = created_at or plan.created_at
        correlation_id = policy_evaluation.correlation_id if policy_evaluation is not None else (context.correlation_id if context is not None else plan.correlation_id)
        trace_id = policy_evaluation.trace_id if policy_evaluation is not None else (context.trace_id if context is not None else plan.trace_id)
        tenant_id = policy_evaluation.tenant_id if policy_evaluation is not None else (context.tenant_id if context is not None else plan.tenant_id)
        lifecycle_state = (
            CognitiveLifecycleState.COMPLETED if selected is not None else CognitiveLifecycleState.ACTIVE
        ) if policy_evaluation is not None else CognitiveLifecycleState.CREATED
        metadata = {"plan_id": plan.plan_id}
        if context is not None:
            metadata["context_id"] = context.context_id
            metadata.update(dict(context.metadata))
        causation_id = plan.plan_id
        if policy_evaluation is not None:
            causation_id = policy_evaluation.evaluation_id
            metadata.update(
                {
                    "policy_evaluation_id": policy_evaluation.evaluation_id,
                    "policy_id": policy_evaluation.policy_id,
                    "policy_version": policy_evaluation.policy_version,
                }
            )
        return CognitiveDecision.create(
            goal,
            options,
            selected_option=selected,
            decision_type=decision_type,
            owner=goal.owner,
            version=goal.version,
            created_at=timestamp,
            lifecycle_state=lifecycle_state,
            rationale=rationale,
            utility=utility,
            risk=risk,
            correlation_id=correlation_id,
            causation_id=causation_id,
            trace_id=trace_id,
            tenant_id=tenant_id,
            metadata=metadata,
        )

    @staticmethod
    def _validate_policy_chain(
        goal: CognitiveGoal,
        plan: CognitivePlan,
        context: CognitiveContext | None,
        policy_evaluation: CognitivePolicyEvaluation,
    ) -> None:
        if not isinstance(policy_evaluation, CognitivePolicyEvaluation):
            raise TypeError("policy_evaluation must be CognitivePolicyEvaluation")
        if not policy_evaluation.allowed:
            raise ValueError("policy evaluation must allow decision")
        if policy_evaluation.goal_id != goal.goal_id:
            raise ValueError("policy evaluation goal_id must match goal_id")
        if policy_evaluation.plan_id != plan.plan_id:
            raise ValueError("policy evaluation plan_id must match plan_id")
        if context is None:
            raise ValueError("context is required when policy_evaluation is provided")
        if policy_evaluation.correlation_id != context.correlation_id:
            raise ValueError("policy evaluation correlation_id must match context")
        if policy_evaluation.trace_id != context.trace_id:
            raise ValueError("policy evaluation trace_id must match context")
        if policy_evaluation.tenant_id != context.tenant_id:
            raise ValueError("policy evaluation tenant_id must match context")


class _DeterministicDecisionBackend:
    __slots__ = ()

    def decide(self, options: tuple[str, ...]) -> str | None:
        if not options:
            return None
        scores = [(option, len(option) % 10 / 10.0) for option in options]
        return max(scores, key=lambda item: item[1])[0]
