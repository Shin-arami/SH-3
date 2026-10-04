from __future__ import annotations

from datetime import UTC, datetime

from foundation.Enums.event import EventType
from foundation.version import EVENT_SCHEMA_VERSION, EVIDENCE_SCHEMA_VERSION
from infrastructure.event_bus import EventBus, EventBusPublisher, EventSubscription
from infrastructure.events import Event
from infrastructure.security import EvidenceRecord, EvidenceStore
from runtime.execution import ExecutionRequest, ExecutionSnapshot, ExecutionState
from runtime.execution_cleanup import RuntimeExecutionCleanupManager
from runtime.execution_controller import RuntimeExecutionController
from runtime.execution_engine import RuntimeExecutionEngine
from runtime.observability import RuntimeExecutionObservability
from runtime.state_machine import RuntimeExecutionStateMachine


def _build_bus() -> tuple[EventBusPublisher, list[Event]]:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    bus.subscribe(
        EventSubscription(
            subscriber_id="runtime-evidence-integration",
            handler=events.append,
            priority=-100,
        ),
    )
    return publisher, events


def _request(execution_id: str, *, timeout: float | None = None) -> ExecutionRequest:
    return ExecutionRequest.create(
        execution_id=execution_id,
        operation="runtime.evidence.integration",
        timeout=timeout,
        correlation_id=f"corr-{execution_id}",
        trace_id=f"trace-{execution_id}",
        tenant_id=f"tenant-{execution_id}",
        metadata={"suite": "part-9-3"},
    )


def _running_snapshot(
    state_machine: RuntimeExecutionStateMachine,
    request: ExecutionRequest,
    now: datetime,
) -> ExecutionSnapshot:
    state_machine.register(ExecutionSnapshot.create(request, now=now))
    state_machine.transition(request.execution_id, ExecutionState.QUEUED, now=now)
    return state_machine.transition(request.execution_id, ExecutionState.RUNNING, now=now)


def _assert_evidence(
    evidence: EvidenceRecord,
    request: ExecutionRequest,
    state: ExecutionState,
) -> None:
    assert evidence.evidence_id == f"runtime.execution:{request.execution_id}"
    assert evidence.kind == "runtime.execution"
    assert evidence.source == "runtime"
    assert evidence.subject_id == request.execution_id
    assert evidence.version == EVIDENCE_SCHEMA_VERSION
    assert evidence.trace_id == request.trace_id
    assert evidence.payload["state"] == state.value
    assert evidence.payload["operation"] == request.operation
    assert evidence.payload["event_schema_version"] == EVENT_SCHEMA_VERSION
    assert evidence.payload["correlation_id"] == request.correlation_id
    assert evidence.payload["trace_id"] == request.trace_id
    assert evidence.payload["tenant_id"] == request.tenant_id
    assert evidence.verify()


def _assert_events(
    events: list[Event],
    request: ExecutionRequest,
    names: list[str],
    types: list[EventType],
) -> None:
    assert [event.name for event in events] == names
    assert [event.event_type for event in events] == types
    for event in events:
        assert event.payload["execution_id"] == request.execution_id
        assert event.correlation_id == request.correlation_id
        assert event.trace_id == request.trace_id
        assert event.metadata.tenant_id == request.tenant_id


def test_completed_execution_evidence_closes_event_contract() -> None:
    publisher, events = _build_bus()
    store = EvidenceStore()
    engine = RuntimeExecutionEngine(event_publisher=publisher, evidence_store=store)
    request = _request("evidence-completed")

    outcome = engine.execute(request, lambda _: {"accepted": "part-9-3"})

    assert outcome.success
    assert outcome.state is ExecutionState.COMPLETED
    evidence = engine.evidence(request.execution_id)
    assert evidence is not None
    _assert_evidence(evidence, request, ExecutionState.COMPLETED)
    assert evidence.payload["result"] == {"accepted": "part-9-3"}
    assert store.verify(evidence.evidence_id)

    runtime_events = [event for event in events if event.name.startswith("RuntimeExecution")]
    _assert_events(
        runtime_events,
        request,
        ["RuntimeExecutionSubmitted", "RuntimeExecutionStarted", "RuntimeExecutionCompleted"],
        [EventType.CREATED, EventType.START, EventType.COMPLETE],
    )
    submitted, started, completed = runtime_events
    assert submitted.causation_id is None
    assert started.causation_id == submitted.id
    assert completed.causation_id == started.id


def test_failed_execution_evidence_closes_error_and_causation_contract() -> None:
    publisher, events = _build_bus()
    store = EvidenceStore()
    engine = RuntimeExecutionEngine(event_publisher=publisher, evidence_store=store)
    request = _request("evidence-failed")

    def fail(_: object) -> None:
        raise ValueError("part-9-3 failure")

    outcome = engine.execute(request, fail)

    assert outcome.failed
    assert outcome.state is ExecutionState.FAILED
    evidence = engine.evidence(request.execution_id)
    assert evidence is not None
    _assert_evidence(evidence, request, ExecutionState.FAILED)
    assert evidence.payload["error_type"] == "ValueError"
    assert evidence.payload["error_message"] == "part-9-3 failure"
    assert evidence.payload["result"] is None
    assert engine.verify_evidence(request.execution_id)

    runtime_events = [event for event in events if event.name.startswith("RuntimeExecution")]
    _assert_events(
        runtime_events,
        request,
        ["RuntimeExecutionSubmitted", "RuntimeExecutionStarted", "RuntimeExecutionFailed"],
        [EventType.CREATED, EventType.START, EventType.FAILURE],
    )
    submitted, started, failed = runtime_events
    assert started.causation_id == submitted.id
    assert failed.causation_id == started.id
    assert failed.payload["error_type"] == "ValueError"
    assert failed.payload["error_message"] == "part-9-3 failure"


def test_cancelled_execution_evidence_is_terminal_and_traceable() -> None:
    publisher, events = _build_bus()
    store = EvidenceStore()
    state_machine = RuntimeExecutionStateMachine()
    controller = RuntimeExecutionController(
        state_machine,
        cleanup_manager=RuntimeExecutionCleanupManager(),
        event_publisher=publisher,
        evidence_store=store,
    )
    request = _request("evidence-cancelled")
    now = datetime(2026, 10, 4, 0, 0, tzinfo=UTC)
    state_machine.register(ExecutionSnapshot.create(request, now=now))

    result = controller.cancel(request.execution_id, now=now)

    assert result.requested
    assert result.state is ExecutionState.CANCELLED
    evidence = controller.evidence(request.execution_id)
    assert evidence is not None
    _assert_evidence(evidence, request, ExecutionState.CANCELLED)
    assert controller.verify_evidence(request.execution_id)
    assert store.records() == (evidence,)
    _assert_events(events, request, ["RuntimeExecutionCancelled"], [EventType.CANCEL])
    assert events[0].causation_id is None


def test_timed_out_execution_evidence_preserves_timeout_contract() -> None:
    publisher, events = _build_bus()
    store = EvidenceStore()
    state_machine = RuntimeExecutionStateMachine()
    controller = RuntimeExecutionController(
        state_machine,
        event_publisher=publisher,
        evidence_store=store,
    )
    request = _request("evidence-timeout", timeout=5.0)
    started_at = datetime(2026, 10, 4, 0, 0, tzinfo=UTC)
    _running_snapshot(state_machine, request, started_at)

    result = controller.timeout(
        request.execution_id,
        now=datetime(2026, 10, 4, 0, 0, 5, tzinfo=UTC),
    )

    assert result.timed_out
    assert result.state is ExecutionState.TIMED_OUT
    evidence = controller.evidence(request.execution_id)
    assert evidence is not None
    _assert_evidence(evidence, request, ExecutionState.TIMED_OUT)
    assert evidence.payload["timeout"] == 5.0
    assert evidence.payload["error_type"] == "TimeoutError"
    assert evidence.payload["error_message"] == "execution timed out"
    assert controller.verify_evidence(request.execution_id)
    _assert_events(events, request, ["RuntimeExecutionTimedOut"], [EventType.TIMEOUT])
    assert events[0].causation_id is None
    assert events[0].payload["timeout"] == 5.0


def test_cleanup_failure_is_retained_in_evidence_and_linked_to_terminal_event() -> None:
    publisher, events = _build_bus()
    store = EvidenceStore()
    cleanup_manager = RuntimeExecutionCleanupManager()
    engine = RuntimeExecutionEngine(
        cleanup_manager=cleanup_manager,
        event_publisher=publisher,
        evidence_store=store,
    )
    request = _request("evidence-cleanup-failure")
    engine.register_cleanup(
        request.execution_id,
        lambda: (_ for _ in ()).throw(RuntimeError("resource release failed")),
        name="resource",
    )

    outcome = engine.execute(request, lambda _: "ok")

    assert outcome.success
    assert outcome.cleanup is not None and outcome.cleanup.failed
    evidence = engine.evidence(request.execution_id)
    assert evidence is not None
    _assert_evidence(evidence, request, ExecutionState.COMPLETED)
    cleanup = evidence.payload["cleanup"]
    assert cleanup["attempted"] is True
    assert cleanup["completed"] is False
    assert cleanup["failed"] is True
    assert cleanup["failures"] == [{
        "name": "resource",
        "error_type": "RuntimeError",
        "error_message": "resource release failed",
    }]

    _assert_events(
        events,
        request,
        [
            "RuntimeExecutionSubmitted",
            "RuntimeExecutionStarted",
            "RuntimeExecutionCompleted",
            "CleanupFailed",
        ],
        [EventType.CREATED, EventType.START, EventType.COMPLETE, EventType.FAILURE],
    )
    assert events[1].causation_id == events[0].id
    assert events[2].causation_id == events[1].id
    assert events[3].causation_id == events[2].id
    assert events[3].payload["failures"][0]["name"] == "resource"


def test_observability_records_only_runtime_execution_evidence_in_shared_store() -> None:
    store = EvidenceStore()
    foreign = EvidenceRecord.create(
        evidence_id="security:test-9-3",
        kind="security",
        source="test",
        subject_id="security-subject",
        payload={"result": "pass"},
        trace_id="trace-security",
        collected_at="2026-10-04T00:00:00+00:00",
    )
    store.register(foreign)
    observability = RuntimeExecutionObservability(store)
    request = _request("evidence-filter")
    snapshot = ExecutionSnapshot.create(
        request,
        now=datetime(2026, 10, 4, 0, 0, tzinfo=UTC),
    )

    evidence = observability.record(snapshot)

    _assert_evidence(evidence, request, ExecutionState.CREATED)
    assert observability.records() == (evidence,)
    assert store.records() == (foreign, evidence)
    assert observability.get(request.execution_id) is evidence
    assert observability.verify(request.execution_id)
    assert store.verify(foreign.evidence_id)
