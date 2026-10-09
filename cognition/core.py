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
from cognition.decision_boundary import CognitiveDecisionBoundary
from cognition.execution_boundary import CognitiveExecutionBoundary
from cognition.feedback import CognitiveFeedback, CognitiveFeedbackStore
from cognition.lifecycle import CognitiveLifecycleStage, CognitiveLifecycleStateMachine
from cognition.observability import CognitionObservability, CognitionObservationReport
from cognition.planning_boundary import CognitivePlanningBoundary
from cognition.policy_boundary import CognitivePolicyBoundary, CognitivePolicyEvaluation
from foundation.utils.hash import short_id
from foundation.utils.logging import info
from foundation.utils.time import iso
from infrastructure.event_bus import EventPublisher
from infrastructure.security import EvidenceStore
from runtime.context_manager import ContextManager
from runtime.execution import ExecutionState

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


def _execution_payload(outcome: Any) -> dict[str, Any]:
    snapshot = outcome.snapshot
    cleanup = outcome.cleanup
    return {
        "execution_id": outcome.execution_id,
        "success": outcome.success,
        "state": outcome.state.value,
        "result": outcome.result,
        "error_type": type(outcome.error).__name__ if outcome.error is not None else None,
        "error_message": str(outcome.error) if outcome.error is not None else None,
        "snapshot": {
            "execution_id": snapshot.execution_id,
            "operation": snapshot.operation,
            "state": snapshot.state.value,
            "created_at": snapshot.created_at.isoformat(),
            "completed_at": snapshot.completed_at.isoformat() if snapshot.completed_at is not None else None,
            "correlation_id": snapshot.correlation_id,
            "causation_id": snapshot.causation_id,
            "trace_id": snapshot.trace_id,
            "tenant_id": snapshot.tenant_id,
            "metadata": dict(snapshot.metadata),
        } if snapshot is not None else None,
        "cleanup": {
            "execution_id": cleanup.execution_id,
            "attempted": cleanup.attempted,
            "completed": cleanup.completed,
            "failed": cleanup.failed,
        } if cleanup is not None else None,
    }


class CognitionCore:
    """SH-3 cognition engine with a typed contract path and legacy compatibility."""

    def __init__(
        self,
        context_manager: ContextManager | None = None,
        planning_boundary: CognitivePlanningBoundary | None = None,
        decision_boundary: CognitiveDecisionBoundary | None = None,
        policy_boundary: CognitivePolicyBoundary | None = None,
        execution_boundary: CognitiveExecutionBoundary | None = None,
        event_publisher: EventPublisher | None = None,
        evidence_store: EvidenceStore | None = None,
        observability: CognitionObservability | None = None,
    ):
        self.cm = context_manager or ContextManager()
        self.planning_boundary = planning_boundary or CognitivePlanningBoundary()
        self.decision_boundary = decision_boundary or CognitiveDecisionBoundary()
        self.policy_boundary = policy_boundary or CognitivePolicyBoundary()
        self.execution_boundary = execution_boundary or CognitiveExecutionBoundary()
        self.observability = observability or CognitionObservability(event_publisher, evidence_store)
        self.feedback_store = CognitiveFeedbackStore()

    def set_event_publisher(self, event_publisher: EventPublisher | None) -> None:
        if event_publisher is not None and not isinstance(event_publisher, EventPublisher):
            raise TypeError("event_publisher must be EventPublisher or None")
        self.observability.set_event_publisher(event_publisher)

    def record_feedback(self, feedback: CognitiveFeedback) -> CognitiveFeedback:
        if not isinstance(feedback, CognitiveFeedback):
            raise TypeError("feedback must be CognitiveFeedback")
        return self.feedback_store.register(feedback)

    def feedback_records(self) -> tuple[CognitiveFeedback, ...]:
        return self.feedback_store.records()

    def latest_feedback(self) -> CognitiveFeedback | None:
        return self.feedback_store.latest()

    def _observe_result(self, result: CognitiveResult) -> CognitiveResult:
        self.observability.observe(result)
        return result

    def observe_result(self, result: CognitiveResult) -> CognitionObservationReport:
        return self.observability.observe(result)

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

    def evaluate_policy_contract(
        self,
        goal: CognitiveGoal,
        plan: CognitivePlan,
        *,
        context: CognitiveContext | None = None,
        created_at: datetime | None = None,
    ) -> CognitivePolicyEvaluation:
        return self.policy_boundary.evaluate(goal, plan, context=context, created_at=created_at)

    def execute_contract(
        self,
        goal: CognitiveGoal | str,
        *,
        context: CognitiveContext | None = None,
        policy: Callable[[list[str]], str | None] | None = None,
        operation: str | None = None,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> CognitiveResult:
        resolved_goal = goal if isinstance(goal, CognitiveGoal) else self.create_goal(goal, created_at=created_at)
        resolved_context = context or self.create_context(resolved_goal)
        timestamp = created_at or resolved_goal.created_at
        lifecycle: CognitiveLifecycleStateMachine | None = None
        plan: CognitivePlan | None = None
        policy_evaluation: CognitivePolicyEvaluation | None = None
        decision: CognitiveDecision | None = None
        try:
            lifecycle = CognitiveLifecycleStateMachine(resolved_goal, context=resolved_context)
            plan = self.plan_contract(resolved_goal, context=resolved_context, created_at=timestamp)
            lifecycle.advance(CognitiveLifecycleStage.PLANNING, causation_id=plan.plan_id, occurred_at=timestamp)
            policy_evaluation = self.policy_boundary.evaluate(resolved_goal, plan, context=resolved_context, created_at=timestamp)
            lifecycle.advance(CognitiveLifecycleStage.POLICY, causation_id=policy_evaluation.evaluation_id, occurred_at=timestamp)
            if not policy_evaluation.allowed:
                lifecycle.advance(CognitiveLifecycleStage.RESULT, lifecycle_state=CognitiveLifecycleState.FAILED, causation_id=policy_evaluation.evaluation_id, occurred_at=timestamp)
                lifecycle_data = lifecycle.to_dict()
                result = CognitiveResult.create(
                    resolved_goal, status=CognitiveResultStatus.FAILURE, lifecycle_state=CognitiveLifecycleState.FAILED, created_at=timestamp,
                    error_type="PolicyDenied", error_message=policy_evaluation.reason, output={"plan": plan.to_dict(), "policy": policy_evaluation.to_dict(), "lifecycle": lifecycle_data},
                    causation_id=policy_evaluation.evaluation_id, correlation_id=policy_evaluation.correlation_id, trace_id=policy_evaluation.trace_id, tenant_id=policy_evaluation.tenant_id,
                    metadata={"context_id": resolved_context.context_id, "policy_evaluation_id": policy_evaluation.evaluation_id, "policy_id": policy_evaluation.policy_id, "lifecycle_id": lifecycle_data["lifecycle_id"]},
                )
                return self._observe_result(result)
            if policy is None:
                decision = self.decision_boundary.decide(resolved_goal, plan, context=resolved_context, policy_evaluation=policy_evaluation, created_at=timestamp)
            else:
                options = list(plan.steps)
                decision_value = policy(options)
                if decision_value is not None and decision_value not in options:
                    raise ValueError("policy decision must be one of the plan options")
                decision = CognitiveDecision.create(
                    resolved_goal, plan.steps, selected_option=decision_value,
                    lifecycle_state=CognitiveLifecycleState.COMPLETED if decision_value is not None else CognitiveLifecycleState.ACTIVE,
                    created_at=timestamp, causation_id=policy_evaluation.evaluation_id, correlation_id=policy_evaluation.correlation_id,
                    trace_id=policy_evaluation.trace_id, tenant_id=policy_evaluation.tenant_id,
                    metadata={"plan_id": plan.plan_id, "policy_evaluation_id": policy_evaluation.evaluation_id, "policy_id": policy_evaluation.policy_id, "policy_version": policy_evaluation.policy_version, "context_id": resolved_context.context_id},
                )
            lifecycle.advance(CognitiveLifecycleStage.DECISION, causation_id=decision.decision_id, occurred_at=timestamp)
            if decision.selected_option is None:
                lifecycle.advance(CognitiveLifecycleStage.RESULT, lifecycle_state=CognitiveLifecycleState.ACTIVE, causation_id=decision.decision_id, occurred_at=timestamp)
                lifecycle_data = lifecycle.to_dict()
                state = CognitiveStateContract.from_goal(
                    resolved_goal, context=resolved_context, steps=plan.steps, results={"decision": None}, lifecycle_state=CognitiveLifecycleState.ACTIVE,
                    created_at=timestamp, updated_at=timestamp, metadata={"plan_id": plan.plan_id, "decision_id": decision.decision_id, "policy_evaluation_id": policy_evaluation.evaluation_id, "lifecycle_id": lifecycle_data["lifecycle_id"]},
                )
                result = CognitiveResult.create(
                    resolved_goal, status=CognitiveResultStatus.PARTIAL, lifecycle_state=CognitiveLifecycleState.ACTIVE, created_at=timestamp,
                    output={"goal": resolved_goal.to_dict(), "plan": plan.to_dict(), "policy": policy_evaluation.to_dict(), "decision": decision.to_dict(), "state": state.to_dict(), "lifecycle": lifecycle_data},
                    causation_id=decision.decision_id, correlation_id=decision.correlation_id, trace_id=decision.trace_id, tenant_id=decision.tenant_id,
                    metadata={"context_id": resolved_context.context_id, "policy_evaluation_id": policy_evaluation.evaluation_id, "policy_id": policy_evaluation.policy_id, "lifecycle_id": lifecycle_data["lifecycle_id"]},
                )
                return self._observe_result(result)
            lifecycle.advance(CognitiveLifecycleStage.EXECUTION, causation_id=decision.decision_id, occurred_at=timestamp)
            outcome = self.execution_boundary.execute(resolved_goal, plan, policy_evaluation, decision, context=resolved_context, operation=operation, payload=payload, created_at=timestamp)
            execution_failed = outcome.failed or outcome.state is not ExecutionState.COMPLETED
            lifecycle_state = CognitiveLifecycleState.FAILED if execution_failed else CognitiveLifecycleState.COMPLETED
            status = CognitiveResultStatus.FAILURE if execution_failed else CognitiveResultStatus.SUCCESS
            execution_payload = _execution_payload(outcome)
            lifecycle.advance(CognitiveLifecycleStage.RESULT, lifecycle_state=lifecycle_state, causation_id=outcome.execution_id, occurred_at=timestamp)
            lifecycle_data = lifecycle.to_dict()
            state = CognitiveStateContract.from_goal(
                resolved_goal, context=resolved_context, steps=plan.steps, results={"decision": decision.selected_option, "execution": execution_payload},
                lifecycle_state=lifecycle_state, created_at=timestamp, updated_at=timestamp, metadata={"plan_id": plan.plan_id, "policy_evaluation_id": policy_evaluation.evaluation_id, "decision_id": decision.decision_id, "execution_id": outcome.execution_id, "lifecycle_id": lifecycle_data["lifecycle_id"]},
            )
            result = CognitiveResult.create(
                resolved_goal, status=status, lifecycle_state=lifecycle_state, created_at=timestamp,
                output={"goal": resolved_goal.to_dict(), "plan": plan.to_dict(), "policy": policy_evaluation.to_dict(), "decision": decision.to_dict(), "execution": execution_payload, "state": state.to_dict(), "lifecycle": lifecycle_data},
                error_type=type(outcome.error).__name__ if outcome.error is not None else None, error_message=str(outcome.error) if outcome.error is not None else None,
                causation_id=outcome.execution_id, correlation_id=decision.correlation_id, trace_id=decision.trace_id, tenant_id=decision.tenant_id,
                metadata={"context_id": resolved_context.context_id, "policy_evaluation_id": policy_evaluation.evaluation_id, "decision_id": decision.decision_id, "execution_id": outcome.execution_id, "lifecycle_id": lifecycle_data["lifecycle_id"]},
            )
            return self._observe_result(result)
        except Exception as exc:
            failure_output: dict[str, Any] = {"goal": resolved_goal.to_dict()}
            if plan is not None:
                failure_output["plan"] = plan.to_dict()
            if policy_evaluation is not None:
                failure_output["policy"] = policy_evaluation.to_dict()
            if decision is not None:
                failure_output["decision"] = decision.to_dict()
            if lifecycle is None:
                lifecycle = CognitiveLifecycleStateMachine(resolved_goal)
            if lifecycle.stage is not CognitiveLifecycleStage.RESULT:
                failure_causation = policy_evaluation.evaluation_id if policy_evaluation is not None else (decision.decision_id if decision is not None else (plan.plan_id if plan is not None else resolved_context.causation_id))
                lifecycle.advance(CognitiveLifecycleStage.RESULT, lifecycle_state=CognitiveLifecycleState.FAILED, causation_id=failure_causation, occurred_at=timestamp)
            lifecycle_data = lifecycle.to_dict()
            failure_output["lifecycle"] = lifecycle_data
            result = CognitiveResult.create(
                resolved_goal, status=CognitiveResultStatus.FAILURE, lifecycle_state=CognitiveLifecycleState.FAILED, created_at=timestamp, output=failure_output,
                error_type=type(exc).__name__, error_message=str(exc),
                correlation_id=policy_evaluation.correlation_id if policy_evaluation is not None else resolved_context.correlation_id,
                causation_id=policy_evaluation.evaluation_id if policy_evaluation is not None else (decision.decision_id if decision is not None else (plan.plan_id if plan is not None else resolved_context.causation_id)),
                trace_id=policy_evaluation.trace_id if policy_evaluation is not None else resolved_context.trace_id, tenant_id=policy_evaluation.tenant_id if policy_evaluation is not None else resolved_context.tenant_id,
                metadata={"context_id": resolved_context.context_id, "lifecycle_id": lifecycle_data["lifecycle_id"], **({"policy_evaluation_id": policy_evaluation.evaluation_id} if policy_evaluation is not None else {}), **({"decision_id": decision.decision_id} if decision is not None else {})},
            )
            return self._observe_result(result)

    def run_contract(
        self,
        goal: CognitiveGoal | str,
        policy: Callable[[list[str]], str | None] | None = None,
        *,
        context: CognitiveContext | None = None,
        created_at: datetime | None = None,
    ) -> CognitiveResult:
        resolved_goal = goal if isinstance(goal, CognitiveGoal) else self.create_goal(goal, created_at=created_at)
        resolved_context = context or self.create_context(resolved_goal)
        timestamp = created_at or resolved_goal.created_at
        lifecycle: CognitiveLifecycleStateMachine | None = None
        policy_evaluation: CognitivePolicyEvaluation | None = None
        plan: CognitivePlan | None = None
        decision: CognitiveDecision | None = None
        try:
            lifecycle = CognitiveLifecycleStateMachine(resolved_goal, context=resolved_context)
            plan = self.plan_contract(resolved_goal, context=resolved_context, created_at=timestamp)
            lifecycle.advance(CognitiveLifecycleStage.PLANNING, causation_id=plan.plan_id, occurred_at=timestamp)
            policy_evaluation = self.policy_boundary.evaluate(resolved_goal, plan, context=resolved_context, created_at=timestamp)
            lifecycle.advance(CognitiveLifecycleStage.POLICY, causation_id=policy_evaluation.evaluation_id, occurred_at=timestamp)
            if not policy_evaluation.allowed:
                lifecycle.advance(CognitiveLifecycleStage.RESULT, lifecycle_state=CognitiveLifecycleState.FAILED, causation_id=policy_evaluation.evaluation_id, occurred_at=timestamp)
                lifecycle_data = lifecycle.to_dict()
                result = CognitiveResult.create(
                    resolved_goal, status=CognitiveResultStatus.FAILURE, lifecycle_state=CognitiveLifecycleState.FAILED, created_at=timestamp,
                    error_type="PolicyDenied", error_message=policy_evaluation.reason, output={"policy": policy_evaluation.to_dict(), "plan": plan.to_dict(), "lifecycle": lifecycle_data},
                    causation_id=policy_evaluation.evaluation_id, correlation_id=policy_evaluation.correlation_id, trace_id=policy_evaluation.trace_id, tenant_id=policy_evaluation.tenant_id,
                    metadata={"context_id": resolved_context.context_id, "policy_evaluation_id": policy_evaluation.evaluation_id, "policy_id": policy_evaluation.policy_id, "lifecycle_id": lifecycle_data["lifecycle_id"]},
                )
                return self._observe_result(result)
            if policy is None:
                decision = self.decision_boundary.decide(resolved_goal, plan, context=resolved_context, policy_evaluation=policy_evaluation, created_at=timestamp)
            else:
                options = list(plan.steps)
                decision_value = policy(options)
                if decision_value is not None and decision_value not in options:
                    raise ValueError("policy decision must be one of the plan options")
                decision = CognitiveDecision.create(
                    resolved_goal, plan.steps, selected_option=decision_value,
                    lifecycle_state=CognitiveLifecycleState.COMPLETED if decision_value is not None else CognitiveLifecycleState.ACTIVE, created_at=timestamp,
                    causation_id=policy_evaluation.evaluation_id, correlation_id=policy_evaluation.correlation_id, trace_id=policy_evaluation.trace_id, tenant_id=policy_evaluation.tenant_id,
                    metadata={"plan_id": plan.plan_id, "policy_evaluation_id": policy_evaluation.evaluation_id, "policy_id": policy_evaluation.policy_id, "policy_version": policy_evaluation.policy_version, "context_id": resolved_context.context_id},
                )
            lifecycle.advance(CognitiveLifecycleStage.DECISION, causation_id=decision.decision_id, occurred_at=timestamp)
            decision_value = decision.selected_option
            lifecycle_state = CognitiveLifecycleState.COMPLETED if decision_value is not None else CognitiveLifecycleState.ACTIVE
            status = CognitiveResultStatus.SUCCESS if decision_value is not None else CognitiveResultStatus.PARTIAL
            lifecycle.advance(CognitiveLifecycleStage.RESULT, lifecycle_state=lifecycle_state, causation_id=decision.decision_id, occurred_at=timestamp)
            lifecycle_data = lifecycle.to_dict()
            state = CognitiveStateContract.from_goal(
                resolved_goal, context=resolved_context, steps=plan.steps, results={"decision": decision_value}, lifecycle_state=lifecycle_state, created_at=timestamp, updated_at=timestamp,
                metadata={"plan_id": plan.plan_id, "decision_id": decision.decision_id, "policy_evaluation_id": policy_evaluation.evaluation_id, "lifecycle_id": lifecycle_data["lifecycle_id"]},
            )
            result = CognitiveResult.create(
                resolved_goal, status=status, lifecycle_state=lifecycle_state, created_at=timestamp,
                output={"goal": resolved_goal.to_dict(), "plan": plan.to_dict(), "policy": policy_evaluation.to_dict(), "decision": decision.to_dict(), "state": state.to_dict(), "lifecycle": lifecycle_data},
                causation_id=decision.decision_id, correlation_id=decision.correlation_id, trace_id=decision.trace_id, tenant_id=decision.tenant_id,
                metadata={"context_id": resolved_context.context_id, "policy_evaluation_id": policy_evaluation.evaluation_id, "policy_id": policy_evaluation.policy_id, "lifecycle_id": lifecycle_data["lifecycle_id"]},
            )
            return self._observe_result(result)
        except Exception as exc:
            failure_output: dict[str, Any] = {"goal": resolved_goal.to_dict()}
            if plan is not None:
                failure_output["plan"] = plan.to_dict()
            if policy_evaluation is not None:
                failure_output["policy"] = policy_evaluation.to_dict()
            if decision is not None:
                failure_output["decision"] = decision.to_dict()
            if lifecycle is None:
                lifecycle = CognitiveLifecycleStateMachine(resolved_goal)
            if lifecycle.stage is not CognitiveLifecycleStage.RESULT:
                failure_causation = policy_evaluation.evaluation_id if policy_evaluation is not None else (decision.decision_id if decision is not None else (plan.plan_id if plan is not None else resolved_context.causation_id))
                lifecycle.advance(CognitiveLifecycleStage.RESULT, lifecycle_state=CognitiveLifecycleState.FAILED, causation_id=failure_causation, occurred_at=timestamp)
            lifecycle_data = lifecycle.to_dict()
            failure_output["lifecycle"] = lifecycle_data
            result = CognitiveResult.create(
                resolved_goal, status=CognitiveResultStatus.FAILURE, lifecycle_state=CognitiveLifecycleState.FAILED, created_at=timestamp, output=failure_output,
                error_type=type(exc).__name__, error_message=str(exc), correlation_id=policy_evaluation.correlation_id if policy_evaluation is not None else resolved_context.correlation_id,
                causation_id=policy_evaluation.evaluation_id if policy_evaluation is not None else (decision.decision_id if decision is not None else (plan.plan_id if plan is not None else resolved_context.causation_id)),
                trace_id=policy_evaluation.trace_id if policy_evaluation is not None else resolved_context.trace_id, tenant_id=policy_evaluation.tenant_id if policy_evaluation is not None else resolved_context.tenant_id,
                metadata={"context_id": resolved_context.context_id, "lifecycle_id": lifecycle_data["lifecycle_id"], **({"policy_evaluation_id": policy_evaluation.evaluation_id, "policy_id": policy_evaluation.policy_id} if policy_evaluation is not None else {})},
            )
            return self._observe_result(result)
