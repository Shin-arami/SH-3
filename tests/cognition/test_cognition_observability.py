from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cognition.contracts import (
    CognitiveContext,
    CognitiveGoal,
    CognitivePlan,
    CognitiveResult,
    CognitiveResultStatus,
)
from cognition.core import CognitionCore
from cognition.execution_boundary import CognitiveExecutionBoundary
from cognition.observability import CognitionObservability, CognitionObservationReport
from cognition.policy_boundary import CognitivePolicyBoundary, CognitivePolicyEvaluation
from infrastructure.event_bus import EventBus, EventBusPublisher, EventSubscription
from infrastructure.events import Event
from infrastructure.security import EvidenceStore
from runtime.execution import ExecutionRequest, ExecutionState
from runtime.execution_engine import ExecutionOperation, ExecutionOutcome

NOW = datetime(2026, 10, 5, 0, 0, tzinfo=UTC)


class StubExecutionBackend:
    def __init__(self, outcome: ExecutionOutcome) -> None:
        self.outcome = outcome
        self.calls = 0

    def execute(self, request: ExecutionRequest, operation: ExecutionOperation | None = None) -> ExecutionOutcome:
        self.calls += 1
        return self.outcome


def _events() -> tuple[EventBusPublisher, EventBus, list[Event]]:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    captured: list[Event] = []
    bus.subscribe(EventSubscription("cognition-observability-test", captured.append, priority=-100))
    return publisher, bus, captured


def test_execute_contract_publishes_complete_cognition_event_chain_and_evidence() -> None:
    publisher, _, events = _events()
    store = EvidenceStore()
    backend = StubExecutionBackend(ExecutionOutcome("exec-obs", True, ExecutionState.COMPLETED, result={"ok": True}))
    cognition = CognitionCore(
        execution_boundary=CognitiveExecutionBoundary(backend),
        event_publisher=publisher,
        evidence_store=store,
    )

    result = cognition.execute_contract("prepare release", operation="op.release", created_at=NOW)

    assert result.status is CognitiveResultStatus.SUCCESS
    cognition_events = [event for event in events if event.name.startswith("Cognition")]
    assert [event.name for event in cognition_events] == [
        "CognitionPolicyEvaluated",
        "CognitionDecisionCreated",
        "CognitionExecutionCompleted",
        "CognitionResultRecorded",
    ]
    assert cognition_events[1].causation_id == cognition_events[0].id
    assert cognition_events[2].causation_id == cognition_events[1].id
    assert cognition_events[3].causation_id == cognition_events[2].id
    assert all(event.correlation_id == result.correlation_id for event in cognition_events)
    assert all(event.trace_id == result.trace_id for event in cognition_events)
    assert all(event.metadata.tenant_id == result.tenant_id for event in cognition_events)
    report = cognition.observe_result(result)
    assert isinstance(report, CognitionObservationReport)
    assert report.result_id == result.result_id
    assert report.successful
    assert len(report.evidence_ids) == 4
    assert all(store.verify(evidence_id) for evidence_id in report.evidence_ids)


def test_observability_records_policy_decision_execution_and_result_evidence() -> None:
    store = EvidenceStore()
    backend = StubExecutionBackend(ExecutionOutcome("exec-evidence", True, ExecutionState.COMPLETED, result="ok"))
    cognition = CognitionCore(execution_boundary=CognitiveExecutionBoundary(backend), evidence_store=store)

    result = cognition.execute_contract("prepare release", operation="op.release", created_at=NOW)
    records = cognition.observability.records()

    assert [record.kind for record in records] == [
        "cognition.policy",
        "cognition.decision",
        "cognition.execution",
        "cognition.result",
    ]
    assert records[-1].subject_id == result.result_id
    assert all(record.trace_id == result.trace_id for record in records)
    assert all(record.verify() for record in records)


def test_run_contract_publishes_policy_decision_result_without_execution() -> None:
    publisher, _, events = _events()
    cognition = CognitionCore(event_publisher=publisher, evidence_store=EvidenceStore())

    result = cognition.run_contract("prepare release", created_at=NOW)

    cognition_events = [event for event in events if event.name.startswith("Cognition")]
    assert [event.name for event in cognition_events] == [
        "CognitionPolicyEvaluated",
        "CognitionDecisionCreated",
        "CognitionResultRecorded",
    ]
    assert cognition_events[1].causation_id == cognition_events[0].id
    assert cognition_events[2].causation_id == cognition_events[1].id
    assert result.status is CognitiveResultStatus.SUCCESS
    assert [record.kind for record in cognition.observability.records()] == [
        "cognition.policy",
        "cognition.decision",
        "cognition.result",
    ]


def test_policy_denial_is_audited_without_decision_or_execution() -> None:
    publisher, _, events = _events()
    store = EvidenceStore()

    class DenyPolicy:
        def evaluate(self, goal: CognitiveGoal, plan: CognitivePlan, context: CognitiveContext) -> CognitivePolicyEvaluation:
            return CognitivePolicyEvaluation.create(goal, plan, allowed=False, context=context, created_at=NOW, reason="blocked")

    cognition = CognitionCore(
        policy_boundary=CognitivePolicyBoundary(DenyPolicy()),
        event_publisher=publisher,
        evidence_store=store,
    )
    result = cognition.execute_contract("prepare release", operation="op.release", created_at=NOW)

    cognition_events = [event for event in events if event.name.startswith("Cognition")]
    assert [event.name for event in cognition_events] == ["CognitionPolicyEvaluated", "CognitionResultRecorded"]
    assert cognition_events[1].causation_id == cognition_events[0].id
    assert result.status is CognitiveResultStatus.FAILURE
    assert [record.kind for record in cognition.observability.records()] == ["cognition.policy", "cognition.result"]
    assert all(record.verify() for record in store.records())


def test_execution_failure_is_published_as_failure_event_and_evidence() -> None:
    publisher, _, events = _events()
    store = EvidenceStore()
    backend = StubExecutionBackend(ExecutionOutcome("exec-failed", False, ExecutionState.FAILED, error=ValueError("failed")))
    cognition = CognitionCore(
        execution_boundary=CognitiveExecutionBoundary(backend),
        event_publisher=publisher,
        evidence_store=store,
    )

    result = cognition.execute_contract("prepare release", operation="op.release", created_at=NOW)

    cognition_events = [event for event in events if event.name.startswith("Cognition")]
    assert cognition_events[2].name == "CognitionExecutionFailed"
    assert cognition_events[2].event_type.value == "failure"
    assert cognition_events[3].causation_id == cognition_events[2].id
    assert result.status is CognitiveResultStatus.FAILURE
    assert store.verify("cognition.execution:exec-failed")
    assert store.verify(f"cognition.result:{result.result_id}")


def test_observability_can_be_used_directly_with_a_typed_result() -> None:
    store = EvidenceStore()
    observability = CognitionObservability(evidence_store=store)
    goal = CognitiveGoal.create("observe only", created_at=NOW)
    result = CognitiveResult.create(goal, status=CognitiveResultStatus.SUCCESS, created_at=NOW, output={"goal": goal.to_dict()})

    report = observability.observe(result)

    assert report.successful
    assert report.event_ids == ()
    assert report.evidence_ids == (f"cognition.result:{result.result_id}",)
    assert observability.verify(report.evidence_ids[0])


def test_observability_rejects_non_result_input() -> None:
    with pytest.raises(TypeError, match="result must be CognitiveResult"):
        CognitionObservability().observe(object())  # type: ignore[arg-type]
