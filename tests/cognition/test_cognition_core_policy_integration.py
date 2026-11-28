from __future__ import annotations

from datetime import UTC, datetime

from cognition.contracts import (
    CognitiveContext,
    CognitiveGoal,
    CognitivePlan,
    CognitiveResultStatus,
)
from cognition.core import CognitionCore
from cognition.decision_boundary import CognitiveDecisionBoundary
from cognition.planner import Planner
from cognition.planning_boundary import CognitivePlanningBoundary
from cognition.policy_boundary import CognitivePolicyBoundary, CognitivePolicyEvaluation

NOW = datetime(2026, 10, 5, 0, 0, tzinfo=UTC)


def test_run_contract_executes_policy_before_decision_and_records_evaluation() -> None:
    calls: list[str] = []

    def backend(goal: CognitiveGoal, plan: CognitivePlan, context: CognitiveContext) -> CognitivePolicyEvaluation:
        calls.append("policy")
        return CognitivePolicyEvaluation.create(
            goal,
            plan,
            allowed=True,
            policy_id="release-policy",
            reason="accepted",
            context=context,
            created_at=NOW,
        )

    cognition = CognitionCore(policy_boundary=CognitivePolicyBoundary(backend))

    def decision(options: tuple[str, ...]) -> str:
        calls.append("decision")
        return options[0]

    cognition.decision_boundary = CognitiveDecisionBoundary(decision)
    result = cognition.run_contract("prepare release", created_at=NOW)

    assert calls == ["policy", "decision"]
    assert result.status is CognitiveResultStatus.SUCCESS
    assert result.output["policy"]["policy_id"] == "release-policy"
    assert result.metadata["policy_evaluation_id"] == result.output["policy"]["evaluation_id"]
    assert result.output["state"]["metadata"]["policy_evaluation_id"] == result.output["policy"]["evaluation_id"]
    assert result.output["decision"]["causation_id"] == result.output["policy"]["evaluation_id"]
    assert result.output["decision"]["lifecycle_state"] == "completed"


def test_run_contract_returns_typed_failure_when_policy_denies() -> None:
    def backend(goal: CognitiveGoal, plan: CognitivePlan, context: CognitiveContext) -> CognitivePolicyEvaluation:
        return CognitivePolicyEvaluation.create(
            goal,
            plan,
            allowed=False,
            policy_id="deny-release",
            reason="release is prohibited",
            context=context,
            created_at=NOW,
        )

    cognition = CognitionCore(policy_boundary=CognitivePolicyBoundary(backend))
    result = cognition.run_contract("prepare release", created_at=NOW)

    assert result.status is CognitiveResultStatus.FAILURE
    assert result.error_type == "PolicyDenied"
    assert result.error_message == "release is prohibited"
    assert result.causation_id == result.output["policy"]["evaluation_id"]
    assert result.metadata["policy_id"] == "deny-release"
    assert result.output["plan"]["plan_id"] == result.output["policy"]["plan_id"]


def test_core_exposes_typed_policy_evaluation_contract() -> None:
    cognition = CognitionCore()
    goal = cognition.create_goal("prepare release", created_at=NOW)
    plan = cognition.plan_contract(goal, created_at=NOW)

    evaluation = cognition.evaluate_policy_contract(goal, plan, created_at=NOW)

    assert evaluation.goal_id == goal.goal_id
    assert evaluation.plan_id == plan.plan_id
    assert evaluation.allowed


def test_run_contract_keeps_legacy_policy_callback_compatible_after_policy_gate() -> None:
    cognition = CognitionCore(
        planning_boundary=CognitivePlanningBoundary(Planner(chunk_size=2))
    )
    result = cognition.run_contract(
        "prepare release today",
        policy=lambda options: options[-1],
        created_at=NOW,
    )

    assert result.status is CognitiveResultStatus.SUCCESS
    assert result.output["decision"]["selected_option"] == "today"
    assert result.output["policy"]["allowed"] is True


def test_run_contract_keeps_typed_string_goal_path() -> None:
    result = CognitionCore().run_contract("prepare release", created_at=NOW)

    assert result.status is CognitiveResultStatus.SUCCESS
    assert result.goal_id == result.output["goal"]["goal_id"]
    assert result.output["policy"]["plan_id"] == result.output["plan"]["plan_id"]


def test_run_contract_uses_policy_evaluation_as_decision_causation_and_lifecycle() -> None:
    cognition = CognitionCore()
    result = cognition.run_contract("prepare release", created_at=NOW)

    policy = result.output["policy"]
    decision = result.output["decision"]
    context = result.output["state"]["context"]

    assert decision["causation_id"] == policy["evaluation_id"]
    assert decision["correlation_id"] == policy["correlation_id"]
    assert decision["trace_id"] == policy["trace_id"]
    assert decision["tenant_id"] == policy["tenant_id"]
    assert decision["lifecycle_state"] == "completed"
    assert decision["metadata"]["context_id"] == context["context_id"]
    assert decision["metadata"]["policy_evaluation_id"] == policy["evaluation_id"]


def test_run_contract_preserves_policy_trace_on_decision_failure() -> None:
    cognition = CognitionCore(
        decision_boundary=CognitiveDecisionBoundary(lambda _: "unknown"),
    )
    result = cognition.run_contract("prepare release", created_at=NOW)

    assert result.status is CognitiveResultStatus.FAILURE
    policy = result.output.get("policy", {})
    assert result.metadata["policy_evaluation_id"] == policy.get("evaluation_id")
    assert result.causation_id == policy.get("evaluation_id")


def test_run_contract_uses_same_context_identity_for_policy_and_decision() -> None:
    cognition = CognitionCore()
    goal = cognition.create_goal(
        "prepare release",
        created_at=NOW,
        correlation_id="corr-ctx",
        trace_id="trace-ctx",
        tenant_id="tenant-ctx",
    )
    context = cognition.create_context(goal, values={"source": "test"})
    result = cognition.run_contract(goal, context=context, created_at=NOW)

    assert result.status is CognitiveResultStatus.SUCCESS
    decision = result.output["decision"]
    assert decision["metadata"]["context_id"] == context.context_id
    assert decision["correlation_id"] == context.correlation_id
    assert decision["trace_id"] == context.trace_id
    assert decision["tenant_id"] == context.tenant_id
