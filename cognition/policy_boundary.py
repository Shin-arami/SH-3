from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock
from types import MappingProxyType
from typing import Any, Protocol

from cognition.contracts import CognitiveContext, CognitiveGoal, CognitivePlan
from foundation.utils.hash import short_id
from foundation.version import COGNITION_CONTRACT_VERSION, validate_semantic_version

__all__ = ["CognitivePolicyBoundary", "CognitivePolicyEvaluation", "PolicyBackend"]


def _validate_text(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _validate_timestamp(value: datetime) -> None:
    if not isinstance(value, datetime):
        raise TypeError("created_at must be datetime")
    if value.tzinfo is None:
        raise ValueError("created_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CognitivePolicyEvaluation:
    evaluation_id: str
    goal_id: str
    plan_id: str
    policy_id: str
    policy_version: str
    allowed: bool
    reason: str
    created_at: datetime
    correlation_id: str
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in (
            ("evaluation_id", self.evaluation_id),
            ("goal_id", self.goal_id),
            ("plan_id", self.plan_id),
            ("policy_id", self.policy_id),
            ("policy_version", self.policy_version),
            ("reason", self.reason),
            ("correlation_id", self.correlation_id),
        ):
            _validate_text(name, value)
        validate_semantic_version(self.policy_version, field="policy_version")
        if not isinstance(self.allowed, bool):
            raise TypeError("allowed must be bool")
        _validate_timestamp(self.created_at)
        for optional_name, optional_value in (("causation_id", self.causation_id), ("trace_id", self.trace_id), ("tenant_id", self.tenant_id)):
            if optional_value is not None:
                _validate_text(optional_name, optional_value)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @classmethod
    def create(
        cls,
        goal: CognitiveGoal,
        plan: CognitivePlan,
        *,
        allowed: bool,
        policy_id: str = "default",
        policy_version: str = COGNITION_CONTRACT_VERSION,
        reason: str = "",
        context: CognitiveContext | None = None,
        created_at: datetime | None = None,
        metadata: Mapping[str, Any] | None = None,
        evaluation_id: str | None = None,
    ) -> CognitivePolicyEvaluation:
        if not isinstance(goal, CognitiveGoal):
            raise TypeError("goal must be CognitiveGoal")
        if not isinstance(plan, CognitivePlan):
            raise TypeError("plan must be CognitivePlan")
        if plan.goal_id != goal.goal_id:
            raise ValueError("plan goal_id must match goal_id")
        if context is not None and context.goal_id != goal.goal_id:
            raise ValueError("context goal_id must match goal_id")
        if not isinstance(allowed, bool):
            raise TypeError("allowed must be bool")
        _validate_text("policy_id", policy_id)
        _validate_text("policy_version", policy_version)
        _validate_text("reason", reason)
        timestamp = created_at or plan.created_at
        correlation_id = context.correlation_id if context is not None else plan.correlation_id
        causation_id = plan.plan_id
        trace_id = context.trace_id if context is not None else plan.trace_id
        tenant_id = context.tenant_id if context is not None else plan.tenant_id
        resolved_metadata = {"plan_id": plan.plan_id}
        if context is not None:
            resolved_metadata["context_id"] = context.context_id
            resolved_metadata.update(dict(context.metadata))
        if metadata is not None:
            resolved_metadata.update(dict(metadata))
        resolved_id = evaluation_id or short_id(
            {
                "goal_id": goal.goal_id,
                "plan_id": plan.plan_id,
                "policy_id": policy_id,
                "policy_version": policy_version,
                "allowed": allowed,
                "reason": reason,
                "created_at": timestamp.isoformat(),
                "correlation_id": correlation_id,
                "causation_id": causation_id,
                "trace_id": trace_id,
                "tenant_id": tenant_id,
                "metadata": resolved_metadata,
            },
            prefix="policy:",
        )
        return cls(
            evaluation_id=resolved_id,
            goal_id=goal.goal_id,
            plan_id=plan.plan_id,
            policy_id=policy_id,
            policy_version=policy_version,
            allowed=allowed,
            reason=reason,
            created_at=timestamp,
            correlation_id=correlation_id,
            causation_id=causation_id,
            trace_id=trace_id,
            tenant_id=tenant_id,
            metadata=resolved_metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "goal_id": self.goal_id,
            "plan_id": self.plan_id,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "allowed": self.allowed,
            "reason": self.reason,
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "metadata": dict(self.metadata),
        }


class PolicyBackend(Protocol):
    def evaluate(
        self,
        goal: CognitiveGoal,
        plan: CognitivePlan,
        context: CognitiveContext,
    ) -> CognitivePolicyEvaluation: ...


class CognitivePolicyBoundary:
    __slots__ = ("_backend", "_lock")

    def __init__(
        self,
        backend: PolicyBackend | Callable[[CognitiveGoal, CognitivePlan, CognitiveContext], CognitivePolicyEvaluation] | None = None,
    ) -> None:
        self._lock = RLock()
        self._backend = backend or _DefaultPolicyBackend()

    @property
    def backend(self) -> PolicyBackend | Callable[[CognitiveGoal, CognitivePlan, CognitiveContext], CognitivePolicyEvaluation]:
        with self._lock:
            return self._backend

    def evaluate(
        self,
        goal: CognitiveGoal,
        plan: CognitivePlan,
        *,
        context: CognitiveContext | None = None,
        created_at: datetime | None = None,
    ) -> CognitivePolicyEvaluation:
        if not isinstance(goal, CognitiveGoal):
            raise TypeError("goal must be CognitiveGoal")
        if not isinstance(plan, CognitivePlan):
            raise TypeError("plan must be CognitivePlan")
        if plan.goal_id != goal.goal_id:
            raise ValueError("plan goal_id must match goal_id")
        resolved_context = context or CognitiveContext.create(
            goal.goal_id,
            correlation_id=goal.correlation_id,
            trace_id=goal.trace_id,
            tenant_id=goal.tenant_id,
        )
        if resolved_context.goal_id != goal.goal_id:
            raise ValueError("context goal_id must match goal_id")
        with self._lock:
            backend = self._backend
            evaluation = (
                backend(goal, plan, resolved_context)
                if callable(backend)
                else backend.evaluate(goal, plan, resolved_context)
            )
        if not isinstance(evaluation, CognitivePolicyEvaluation):
            raise TypeError("policy backend result must be CognitivePolicyEvaluation")
        if evaluation.goal_id != goal.goal_id:
            raise ValueError("policy evaluation goal_id must match goal_id")
        if evaluation.plan_id != plan.plan_id:
            raise ValueError("policy evaluation plan_id must match plan_id")
        return evaluation


class _DefaultPolicyBackend:
    __slots__ = ()

    def evaluate(
        self,
        goal: CognitiveGoal,
        plan: CognitivePlan,
        context: CognitiveContext,
    ) -> CognitivePolicyEvaluation:
        return CognitivePolicyEvaluation.create(
            goal,
            plan,
            allowed=True,
            policy_id="default",
            reason="Default cognitive policy accepted",
            context=context,
            created_at=plan.created_at,
            metadata={"mode": "compatibility"},
        )
