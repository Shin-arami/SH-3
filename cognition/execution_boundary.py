from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from threading import RLock
from typing import Any, Protocol

from cognition.contracts import CognitiveContext, CognitiveDecision, CognitiveGoal, CognitivePlan
from cognition.policy_boundary import CognitivePolicyEvaluation
from foundation.utils.hash import short_id
from runtime.execution import ExecutionRequest
from runtime.execution_engine import ExecutionOperation, ExecutionOutcome, RuntimeExecutionEngine

__all__ = ["CognitiveExecutionBoundary", "ExecutionBackend"]


class ExecutionBackend(Protocol):
    def execute(self, request: ExecutionRequest, operation: ExecutionOperation | None = None) -> ExecutionOutcome: ...


def _validate_text(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _execution_snapshot(snapshot: Any) -> dict[str, Any]:
    if snapshot is None:
        return {}
    return {
        "execution_id": snapshot.execution_id,
        "operation": snapshot.operation,
        "state": snapshot.state.value,
        "priority": snapshot.priority.value,
        "created_at": snapshot.created_at.isoformat(),
        "queued_at": snapshot.queued_at.isoformat() if snapshot.queued_at is not None else None,
        "started_at": snapshot.started_at.isoformat() if snapshot.started_at is not None else None,
        "completed_at": snapshot.completed_at.isoformat() if snapshot.completed_at is not None else None,
        "timeout": snapshot.timeout,
        "attempt": snapshot.attempt,
        "result": snapshot.result,
        "error_type": snapshot.error_type,
        "error_message": snapshot.error_message,
        "correlation_id": snapshot.correlation_id,
        "causation_id": snapshot.causation_id,
        "trace_id": snapshot.trace_id,
        "tenant_id": snapshot.tenant_id,
        "metadata": dict(snapshot.metadata),
        "event_schema_version": snapshot.event_schema_version,
    }


def _execution_output(outcome: ExecutionOutcome) -> dict[str, Any]:
    return {
        "execution_id": outcome.execution_id,
        "success": outcome.success,
        "state": outcome.state.value,
        "result": outcome.result,
        "error_type": type(outcome.error).__name__ if outcome.error is not None else None,
        "error_message": str(outcome.error) if outcome.error is not None else None,
        "snapshot": _execution_snapshot(outcome.snapshot),
        "cleanup": {
            "execution_id": outcome.cleanup.execution_id,
            "attempted": outcome.cleanup.attempted,
            "completed": outcome.cleanup.completed,
            "failed": outcome.cleanup.failed,
            "failures": [
                {
                    "name": failure.name,
                    "error_type": failure.error_type,
                    "error_message": failure.error_message,
                }
                for failure in outcome.cleanup.failures
            ],
        } if outcome.cleanup is not None else None,
    }


class CognitiveExecutionBoundary:
    """Typed bridge from cognitive decisions to runtime execution."""

    __slots__ = ("_backend", "_lock")

    def __init__(self, backend: ExecutionBackend | Callable[[ExecutionRequest, ExecutionOperation | None], ExecutionOutcome] | None = None) -> None:
        self._lock = RLock()
        self._backend = backend or RuntimeExecutionEngine()

    @property
    def backend(self) -> ExecutionBackend | Callable[[ExecutionRequest, ExecutionOperation | None], ExecutionOutcome]:
        with self._lock:
            return self._backend

    def execute(
        self,
        goal: CognitiveGoal,
        plan: CognitivePlan,
        policy_evaluation: CognitivePolicyEvaluation,
        decision: CognitiveDecision,
        *,
        context: CognitiveContext | None = None,
        operation: str | None = None,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> ExecutionOutcome:
        self._validate_contract(goal, plan, policy_evaluation, decision, context)
        if not policy_evaluation.allowed:
            raise ValueError("policy evaluation must allow execution")
        if decision.selected_option is None:
            raise ValueError("decision must select an option before execution")
        selected_operation = operation or decision.selected_option
        _validate_text("operation", selected_operation)
        timestamp = created_at or decision.created_at
        execution_id = short_id(
            {
                "goal_id": goal.goal_id,
                "plan_id": plan.plan_id,
                "policy_evaluation_id": policy_evaluation.evaluation_id,
                "decision_id": decision.decision_id,
                "context_id": context.context_id if context is not None else None,
                "operation": selected_operation,
                "created_at": timestamp.isoformat(),
            },
            prefix="cognitive.execution:",
        )
        request_payload = {
            "goal_id": goal.goal_id,
            "plan_id": plan.plan_id,
            "policy_evaluation_id": policy_evaluation.evaluation_id,
            "decision_id": decision.decision_id,
            "context_id": context.context_id if context is not None else None,
            "selected_option": decision.selected_option,
            **(dict(payload) if payload is not None else {}),
        }
        request = ExecutionRequest.create(
            execution_id=execution_id,
            operation=selected_operation,
            payload=request_payload,
            correlation_id=decision.correlation_id,
            causation_id=decision.decision_id,
            trace_id=decision.trace_id,
            tenant_id=decision.tenant_id,
            metadata={
                "goal_id": goal.goal_id,
                "plan_id": plan.plan_id,
                "policy_evaluation_id": policy_evaluation.evaluation_id,
                "decision_id": decision.decision_id,
                "context_id": context.context_id if context is not None else None,
            },
        )
        with self._lock:
            backend = self._backend
            return backend(request, None) if callable(backend) else backend.execute(request)

    @staticmethod
    def _validate_contract(
        goal: CognitiveGoal,
        plan: CognitivePlan,
        policy_evaluation: CognitivePolicyEvaluation,
        decision: CognitiveDecision,
        context: CognitiveContext | None,
    ) -> None:
        if not isinstance(goal, CognitiveGoal):
            raise TypeError("goal must be CognitiveGoal")
        if not isinstance(plan, CognitivePlan):
            raise TypeError("plan must be CognitivePlan")
        if not isinstance(policy_evaluation, CognitivePolicyEvaluation):
            raise TypeError("policy_evaluation must be CognitivePolicyEvaluation")
        if not isinstance(decision, CognitiveDecision):
            raise TypeError("decision must be CognitiveDecision")
        if context is not None and not isinstance(context, CognitiveContext):
            raise TypeError("context must be CognitiveContext")
        if plan.goal_id != goal.goal_id:
            raise ValueError("plan goal_id must match goal_id")
        if policy_evaluation.goal_id != goal.goal_id:
            raise ValueError("policy evaluation goal_id must match goal_id")
        if policy_evaluation.plan_id != plan.plan_id:
            raise ValueError("policy evaluation plan_id must match plan_id")
        if decision.goal_id != goal.goal_id:
            raise ValueError("decision goal_id must match goal_id")
        if decision.causation_id != policy_evaluation.evaluation_id:
            raise ValueError("decision causation_id must match policy evaluation")
        if decision.correlation_id != policy_evaluation.correlation_id:
            raise ValueError("decision correlation_id must match policy evaluation")
        if decision.trace_id != policy_evaluation.trace_id:
            raise ValueError("decision trace_id must match policy evaluation")
        if decision.tenant_id != policy_evaluation.tenant_id:
            raise ValueError("decision tenant_id must match policy evaluation")
        if context is not None:
            if context.goal_id != goal.goal_id:
                raise ValueError("context goal_id must match goal_id")
            if context.correlation_id != decision.correlation_id:
                raise ValueError("context correlation_id must match decision")
            if context.trace_id != decision.trace_id:
                raise ValueError("context trace_id must match decision")
            if context.tenant_id != decision.tenant_id:
                raise ValueError("context tenant_id must match decision")
