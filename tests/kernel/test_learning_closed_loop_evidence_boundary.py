from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event as ThreadEvent
from typing import cast

import pytest

from cognition.contracts import (
    CognitiveGoal,
    CognitiveLifecycleState,
    CognitiveResult,
    CognitiveResultStatus,
)
from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.version import EVENT_SCHEMA_VERSION, EVIDENCE_SCHEMA_VERSION
from infrastructure.event_bus import EventBus, EventBusPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from infrastructure.events.catalog import CanonicalEventCatalog
from infrastructure.security import EvidenceRecord, EvidenceStore
from kernel import SH3Kernel
from kernel.learning_closed_loop_evidence_boundary import (
    LearningClosedLoopEvidenceBoundary,
    LearningClosedLoopEvidenceResult,
)
from kernel.learning_feedback_loop import (
    ClosedLoopStatus,
    LearningClosedLoopCoordinator,
    LearningClosedLoopReport,
)

NOW = datetime(2026, 10, 9, 0, 0, tzinfo=UTC)

#         "prepare release",
def _result(
    result_id: str = "result:closed-loop-evidence",
    *,
    intent: str = "closed-loop evidence",
) -> CognitiveResult:
    goal = CognitiveGoal.create(
        intent,
        created_at=NOW,
        correlation_id="corr-closed-loop-evidence",
        trace_id="trace-closed-loop-evidence",
        tenant_id="tenant-closed-loop-evidence",
    )
    return CognitiveResult.create(
        goal,
        status=CognitiveResultStatus.SUCCESS,
        lifecycle_state=CognitiveLifecycleState.COMPLETED,
        created_at=NOW,
        output={
            "goal": goal.to_dict(),
            "plan": {"plan_id": "plan:closed-loop-evidence", "steps": ["prepare release"]},
            "decision": {"decision_id": "decision:closed-loop-evidence", "selected_option": "prepare release"},
        },
        result_id=result_id,
    )


def _context() -> EventPropagationContext:
    return EventPropagationContext.create(
        correlation_id="corr-closed-loop-evidence",
        causation_id="cause-closed-loop-evidence",
        trace_id="trace-closed-loop-evidence",
        tenant_id="tenant-closed-loop-evidence",
    )


def test_kernel_owns_closed_loop_evidence_boundary_and_shares_store() -> None:
    kernel = SH3Kernel()
    boundary = kernel.learning_closed_loop_evidence_boundary

    assert isinstance(boundary, LearningClosedLoopEvidenceBoundary)
    assert boundary.evidence_store is kernel.optimizer_evidence_boundary.evidence_store
    assert boundary is kernel.learning_feedback_loop._closed_loop_evidence_boundary


def test_successful_cycle_records_integrity_protected_terminal_evidence() -> None:
    kernel = SH3Kernel()
    report = kernel.learning_feedback_loop.run(_result(), optimize=False)

    outcome = kernel.learning_closed_loop_evidence_boundary.get(report.cycle_id)

    assert outcome is not None
    assert outcome.recorded is True
    assert outcome.evidence is not None
    assert outcome.evidence.kind == "learning.closed_loop"
    assert outcome.evidence.source == "kernel.learning_feedback_loop"
    assert outcome.evidence.subject_id == report.result_id
    assert outcome.evidence.version == EVIDENCE_SCHEMA_VERSION
    assert outcome.evidence.payload["event_schema_version"] == EVENT_SCHEMA_VERSION
    assert outcome.evidence.payload["status"] == ClosedLoopStatus.COMPLETED.value
    assert outcome.evidence.payload["cycle_success"] is True
    assert outcome.evidence.payload["fully_successful"] is True
    assert outcome.evidence.payload["success_semantics"]["learning"] is True
    assert outcome.evidence.verify()
    assert kernel.learning_closed_loop_evidence_boundary.evidence_store.verify(
        outcome.evidence.evidence_id
    )


def test_failed_cycle_is_recorded_with_failure_semantics() -> None:
    kernel = SH3Kernel()
    result = _result("result:failed-closed-loop-evidence")
    failed = CognitiveResult.create(
        result.goal_id,
        status=CognitiveResultStatus.FAILURE,
        lifecycle_state=CognitiveLifecycleState.FAILED,
        output=result.output,
        result_id=result.result_id,
        correlation_id=result.correlation_id,
        trace_id=result.trace_id,
        tenant_id=result.tenant_id,
        created_at=NOW,
        error_type="RuntimeError",
        error_message="intentional failure",
    )

    report = kernel.learning_feedback_loop.run(failed, optimize=False, recover=False)
    outcome = kernel.learning_closed_loop_evidence_boundary.get(report.cycle_id)

    assert report.status is ClosedLoopStatus.FAILED
    assert outcome is not None and outcome.recorded and outcome.evidence is not None
    assert outcome.evidence.payload["cycle_success"] is False
    assert outcome.evidence.payload["fully_successful"] is False
    assert outcome.evidence.payload["recovered"] is False


def test_recovered_cycle_is_distinguished_from_fully_successful_cycle() -> None:
    kernel = SH3Kernel()
    result = _result("result:recovered-closed-loop-evidence")
    failed = CognitiveResult.create(
        result.goal_id,
        status=CognitiveResultStatus.FAILURE,
        lifecycle_state=CognitiveLifecycleState.FAILED,
        output=result.output,
        result_id=result.result_id,
        correlation_id=result.correlation_id,
        trace_id=result.trace_id,
        tenant_id=result.tenant_id,
        created_at=NOW,
        error_type="RuntimeError",
        error_message="recovery required",
    )

    report = kernel.learning_feedback_loop.run(failed, optimize=False, recover=True)
    outcome = kernel.learning_closed_loop_evidence_boundary.get(report.cycle_id)

    assert report.status is ClosedLoopStatus.RECOVERED
    assert outcome is not None and outcome.evidence is not None
    assert outcome.evidence.payload["cycle_success"] is True
    assert outcome.evidence.payload["fully_successful"] is False
    assert outcome.evidence.payload["recovered"] is True


def test_closed_loop_evidence_links_material_optimizer_evidence() -> None:
    kernel = SH3Kernel()
    for index in range(7):
        kernel.context_manager.push(f"closed-loop-context-{index}")

    report = kernel.learning_feedback_loop.run(_result(), context=_context(), optimize=True)
    outcome = kernel.learning_closed_loop_evidence_boundary.get(report.cycle_id)

    assert outcome is not None and outcome.recorded and outcome.evidence is not None
    update = report.optimization_result
    assert update is not None and update["update"]["changed"] is True
    linked_ids = outcome.evidence.payload["related_optimization_evidence_ids"]
    assert linked_ids
    optimizer_evidence = {
        record.evidence_id
        for record in kernel.optimizer_evidence_boundary.evidence_store.records()
        if record.kind == "optimization"
    }
    assert set(linked_ids) <= optimizer_evidence
    assert outcome.evidence.payload["correlation_id"] == _context().correlation_id
    assert outcome.evidence.trace_id == _context().trace_id


def test_evidence_event_is_causally_linked_to_terminal_cycle_event() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    bus.subscribe(
        EventSubscription(
            subscriber_id="closed-loop-evidence-audit",
            handler=events.append,
            priority=-100,
        )
    )
    kernel = SH3Kernel(event_publisher=publisher)

    report = kernel.learning_feedback_loop.run(_result(), context=_context(), optimize=False)

    terminal = next(
        event
        for event in events
        if event.name in {"LearningClosedLoopCompleted", "LearningClosedLoopFailed"}
        and event.payload.get("cycle_id") == report.cycle_id
    )
    feedback_recorded = next(
        event
        for event in events
        if event.name == "CognitiveFeedbackRecorded"
        and isinstance(event.payload.get("feedback"), Mapping)
        and event.payload["feedback"].get("cycle_id") == report.cycle_id
    )
    recorded = next(
        event
        for event in events
        if event.name == "LearningClosedLoopEvidenceRecorded"
        and event.payload.get("cycle_id") == report.cycle_id
    )
    assert terminal.causation_id == feedback_recorded.id
    assert recorded.category is Category.LEARNING
    assert recorded.event_type is EventType.CREATED
    assert recorded.causation_id == terminal.id
    assert recorded.correlation_id == terminal.correlation_id
    assert recorded.trace_id == terminal.trace_id
    assert recorded.metadata.tenant_id == terminal.metadata.tenant_id


def test_canonical_catalog_validates_terminal_and_evidence_events() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    bus.subscribe(
        EventSubscription(
            subscriber_id="closed-loop-catalog-audit",
            handler=events.append,
            priority=-100,
        )
    )
    kernel = SH3Kernel(event_publisher=publisher)
    report = kernel.learning_feedback_loop.run(_result(), optimize=False)
    catalog = CanonicalEventCatalog()

    relevant = tuple(
        event
        for event in events
        if event.name
        in {"LearningClosedLoopStarted", "LearningClosedLoopCompleted", "LearningClosedLoopEvidenceRecorded"}
        and event.payload.get("cycle_id") == report.cycle_id
    )
    assert {event.name for event in relevant} == {
        "LearningClosedLoopStarted",
        "LearningClosedLoopCompleted",
        "LearningClosedLoopEvidenceRecorded",
    }
    for event in relevant:
        catalog.validate(event)


def test_duplicate_record_returns_same_evidence_result() -> None:
    kernel = SH3Kernel()
    report = kernel.learning_feedback_loop.run(_result(), optimize=False)
    boundary = kernel.learning_closed_loop_evidence_boundary

    first = boundary.record(report, context=_context(), created_at=NOW)
    second = boundary.record(report, context=_context(), created_at=NOW)

    assert first is second
    assert len(boundary.records()) == 1
    assert sum(
        record.kind == "learning.closed_loop" for record in boundary.evidence_store.records()
    ) == 1


def test_concurrent_cycle_requests_execute_and_record_once() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    entered = ThreadEvent()
    release = ThreadEvent()
    events: list[Event] = []

    def pause_first_cycle(event: Event) -> None:
        if event.name == "LearningClosedLoopStarted":
            entered.set()
            release.wait(timeout=3)

    bus.subscribe(
        EventSubscription(
            subscriber_id="closed-loop-concurrency-gate",
            handler=pause_first_cycle,
            event_name="LearningClosedLoopStarted",
            priority=1000,
        )
    )
    bus.subscribe(
        EventSubscription(
            subscriber_id="closed-loop-concurrency-audit",
            handler=events.append,
            priority=-100,
        )
    )
    kernel = SH3Kernel(event_publisher=publisher)
    result = _result("result:concurrent-closed-loop")

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            executor.submit(kernel.learning_feedback_loop.run, result, optimize=False)
            for _ in range(8)
        ]
        assert entered.wait(timeout=3)
        release.set()
        reports = tuple(future.result(timeout=5) for future in futures)

    assert all(report is reports[0] for report in reports)
    assert len(kernel.learning_feedback_loop.records()) == 1
    assert len(kernel.learning_closed_loop_evidence_boundary.records()) == 1
    assert sum(event.name == "LearningClosedLoopStarted" for event in events) == 1
    assert sum(event.name == "LearningClosedLoopEvidenceRecorded" for event in events) == 1


def test_publisher_free_path_records_evidence() -> None:
    kernel = SH3Kernel()
    report = kernel.learning_feedback_loop.run(_result(), optimize=False)

    outcome = kernel.learning_closed_loop_evidence_boundary.get(report.cycle_id)

    assert outcome is not None and outcome.recorded and outcome.evidence is not None
    assert kernel.learning_closed_loop_evidence_boundary.evidence_store.verify(
        outcome.evidence.evidence_id
    )


def test_invalid_report_type_is_rejected() -> None:
    boundary = LearningClosedLoopEvidenceBoundary()

    with pytest.raises(TypeError, match="report must be LearningClosedLoopReport"):
        boundary.record(cast(LearningClosedLoopReport, object()))


def test_event_publisher_replacement_uses_new_publisher() -> None:
    first_bus = EventBus()
    second_bus = EventBus()
    first_publisher = EventBusPublisher(first_bus)
    second_publisher = EventBusPublisher(second_bus)
    first_events: list[Event] = []
    second_events: list[Event] = []
    first_bus.subscribe(EventSubscription(subscriber_id="first-audit", handler=first_events.append, priority=-100))
    second_bus.subscribe(EventSubscription(subscriber_id="second-audit", handler=second_events.append, priority=-100))
    kernel = SH3Kernel(event_publisher=first_publisher)
    report = kernel.learning_feedback_loop.run(_result("result:publisher-rebind"), optimize=False)

    kernel.set_event_publisher(second_publisher)
    next_report = kernel.learning_feedback_loop.run(
        _result(
            "result:publisher-rebind-next",
            intent="closed-loop evidence after publisher replacement",
        ),
        optimize=False,
    )
    assert kernel.learning_closed_loop_evidence_boundary.get(report.cycle_id) is not None
    assert next_report.cycle_id != report.cycle_id
    assert any(event.name == "LearningClosedLoopEvidenceRecorded" for event in first_events)
    assert any(event.name == "LearningClosedLoopEvidenceRecorded" for event in second_events)


def test_evidence_commit_then_raise_is_reconciled_as_success() -> None:
    class CommitThenRaiseEvidenceStore(EvidenceStore):
        def register(self, record: EvidenceRecord) -> EvidenceRecord:
            super().register(record)
            raise RuntimeError("evidence committed but acknowledgement failed")

    kernel = SH3Kernel()
    report = kernel.learning_feedback_loop.run(
        _result("result:commit-then-raise"),
        optimize=False,
    )
    store = CommitThenRaiseEvidenceStore()
    boundary = LearningClosedLoopEvidenceBoundary(store)

    outcome = boundary.record(report, context=_context(), created_at=NOW)

    assert outcome.recorded is True
    assert outcome.evidence is not None
    assert outcome.evidence.verify()
    assert store.get(outcome.evidence.evidence_id) == outcome.evidence
    assert outcome.metadata["write_error_reconciled"] is True
    assert len(store.records()) == 1


def test_evidence_write_failure_marks_cycle_failed_and_retries_without_reexecution() -> None:
    class FailThreeTimesEvidenceStore(EvidenceStore):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def register(self, record: EvidenceRecord) -> EvidenceRecord:
            self.calls += 1
            if self.calls <= 3:
                raise ValueError("temporary evidence store failure")
            return super().register(record)

    kernel = SH3Kernel()
    store = FailThreeTimesEvidenceStore()
    evidence_boundary = LearningClosedLoopEvidenceBoundary(store)
    coordinator = LearningClosedLoopCoordinator(
        kernel,
        closed_loop_evidence_boundary=evidence_boundary,
    )
    result = _result("result:retry-evidence-write")

    first = coordinator.run(result, optimize=False)

    assert first.status is ClosedLoopStatus.FAILED
    assert first.failure_detail["evidence_error"] == "temporary evidence store failure"
    assert store.calls == 3
    pending = evidence_boundary.get(first.cycle_id)
    assert pending is not None
    assert pending.recorded is False

    retried = coordinator.run(result, optimize=False)

    assert retried is first
    assert store.calls == 4
    recorded = evidence_boundary.get(first.cycle_id)
    assert recorded is not None and recorded.recorded
    assert recorded.evidence is not None
    assert recorded.evidence.payload["status"] == ClosedLoopStatus.FAILED.value
    assert (
        recorded.evidence.payload["failure_detail"]["evidence_error"]
        == "temporary evidence store failure"
    )
    assert len(coordinator.records()) == 1
    assert len(store.records()) == 1


def test_evidence_failure_is_reported_as_typed_boundary_result() -> None:
    class FailingEvidenceStore(EvidenceStore):
        def register(self, record: EvidenceRecord) -> EvidenceRecord:
            raise ValueError("evidence store unavailable")

    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    bus.subscribe(
        EventSubscription(
            subscriber_id="closed-loop-evidence-failure-audit",
            handler=events.append,
            priority=-100,
        )
    )
    kernel = SH3Kernel()
    report = kernel.learning_feedback_loop.run(_result("result:failing-evidence-store"), optimize=False)
    boundary = LearningClosedLoopEvidenceBoundary(FailingEvidenceStore(), publisher)

    outcome = boundary.record(report, context=_context(), created_at=NOW)

    assert isinstance(outcome, LearningClosedLoopEvidenceResult)
    assert outcome.recorded is False
    assert outcome.evidence is None
    assert outcome.error == "evidence store unavailable"
    failed = next(event for event in events if event.name == "LearningClosedLoopEvidenceFailed")
    assert failed.category is Category.LEARNING
    assert failed.event_type is EventType.FAILURE
    CanonicalEventCatalog().validate(failed)


def test_parallel_closed_loops_keep_trace_context_isolated() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []

    bus.subscribe(
        EventSubscription(
            subscriber_id="parallel-closed-loop-audit",
            handler=events.append,
            priority=-100,
        )
    )
    kernel = SH3Kernel(event_publisher=publisher)

    contexts = (
        EventPropagationContext.create(
            "part11-11-correlation-a",
            causation_id="part11-11-cause-a",
            trace_id="part11-11-trace-a",
            tenant_id="part11-11-tenant-a",
        ),
        EventPropagationContext.create(
            "part11-11-correlation-b",
            causation_id="part11-11-cause-b",
            trace_id="part11-11-trace-b",
            tenant_id="part11-11-tenant-b",
        ),
    )

    results = (
        _result("result:parallel-a", intent="parallel closed loop a"),
        _result("result:parallel-b", intent="parallel closed loop b"),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = tuple(
            executor.submit(
                kernel.learning_feedback_loop.run,
                result,
                context=context,
                optimize=True,
                recover=True,
            )
            for result, context in zip(results, contexts, strict=True)
        )
        reports = tuple(future.result() for future in futures)

    for report, context in zip(reports, contexts, strict=True):
        assert report.correlation_id == context.correlation_id
        assert report.trace_id == context.trace_id
        assert report.tenant_id == context.tenant_id

        terminal = next(
            event
            for event in events
            if event.name
            in {"LearningClosedLoopCompleted", "LearningClosedLoopFailed"}
            and event.payload.get("cycle_id") == report.cycle_id
        )
        recorded = next(
            event
            for event in events
            if event.name == "LearningClosedLoopEvidenceRecorded"
            and event.payload.get("cycle_id") == report.cycle_id
        )

        assert terminal.correlation_id == context.correlation_id
        assert terminal.trace_id == context.trace_id
        assert terminal.metadata.tenant_id == context.tenant_id

        assert recorded.causation_id == terminal.id
        assert recorded.correlation_id == terminal.correlation_id
        assert recorded.trace_id == terminal.trace_id
        assert recorded.metadata.tenant_id == terminal.metadata.tenant_id

    assert reports[0].cycle_id != reports[1].cycle_id
    assert reports[0].result_id != reports[1].result_id


def test_closed_loop_evidence_does_not_link_optimization_records_across_tenants() -> None:
    kernel = SH3Kernel()
    context = EventPropagationContext.create(
        correlation_id="shared-correlation:tenant-isolation",
        causation_id="cause:tenant-a",
        trace_id="shared-trace:tenant-isolation",
        tenant_id="tenant-a",
    )
    store = kernel.learning_closed_loop_evidence_boundary.evidence_store

    for evidence_id, tenant_id in (
        ("optimization:tenant-a", "tenant-a"),
        ("optimization:tenant-b", "tenant-b"),
    ):
        store.register(
            EvidenceRecord.create(
                evidence_id=evidence_id,
                kind="optimization",
                source="test.optimization",
                subject_id=f"subject:{tenant_id}",
                collected_at=NOW.isoformat(),
                trace_id=context.trace_id,
                payload={
                    "correlation_id": context.correlation_id,
                    "tenant_id": tenant_id,
                },
            )
        )

    report = kernel.learning_feedback_loop.run(
        _result("result:tenant-isolation"),
        context=context,
        optimize=False,
    )
    outcome = kernel.learning_closed_loop_evidence_boundary.get(report.cycle_id)

    assert outcome is not None and outcome.evidence is not None
    assert outcome.evidence.payload["related_optimization_evidence_ids"] == [
        "optimization:tenant-a"
    ]
