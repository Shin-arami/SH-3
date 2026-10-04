from __future__ import annotations

from infrastructure.event_bus import EventBus, EventBusPublisher, EventSubscription
from infrastructure.events import Event
from infrastructure.security import EvidenceStore
from runtime.execution_engine import RuntimeExecutionEngine


def _build_engine() -> tuple[RuntimeExecutionEngine, list[Event], EvidenceStore]:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    store = EvidenceStore()
    bus.subscribe(
        EventSubscription(
            subscriber_id="runtime-observability-test",
            handler=events.append,
            priority=-100,
        ),
    )
    engine = RuntimeExecutionEngine(
        event_publisher=publisher,
        evidence_store=store,
    )
    return engine, events, store


def test_completed_execution_evidence_matches_runtime_events() -> None:
    engine, events, store = _build_engine()
    request = engine.create_request(
        "runtime.observability.completed",
        {"value": 1},
    )

    outcome = engine.execute(
        request,
        lambda payload: {"value": payload["value"] + 1},
    )

    assert outcome.success
    evidence = engine.evidence(request.execution_id)
    assert evidence is not None
    assert evidence.kind == "runtime.execution"
    assert evidence.source == "runtime"
    assert evidence.subject_id == request.execution_id
    assert evidence.payload["state"] == "completed"
    assert evidence.payload["result"] == {"value": 2}
    assert evidence.verify()
    assert store.verify(evidence.evidence_id)

    runtime_events = [
        event
        for event in events
        if event.name.startswith("RuntimeExecution")
    ]
    assert [event.name for event in runtime_events] == [
        "RuntimeExecutionSubmitted",
        "RuntimeExecutionStarted",
        "RuntimeExecutionCompleted",
    ]
    assert all(
        event.payload["execution_id"] == request.execution_id
        for event in runtime_events
    )
    assert all(
        event.metadata.correlation_id == request.correlation_id
        for event in runtime_events
    )


def test_failed_execution_evidence_contains_error() -> None:
    engine, events, store = _build_engine()
    request = engine.create_request("runtime.observability.failed")

    def fail(_: object) -> None:
        raise ValueError("observability failure")

    outcome = engine.execute(request, fail)

    assert not outcome.success
    assert outcome.state.value == "failed"

    evidence = engine.evidence(request.execution_id)
    assert evidence is not None
    assert evidence.kind == "runtime.execution"
    assert evidence.source == "runtime"
    assert evidence.payload["state"] == "failed"
    assert evidence.payload["error_type"] == "ValueError"
    assert evidence.payload["error_message"] == "observability failure"
    assert evidence.verify()
    assert store.verify(evidence.evidence_id)

    failure_events = [
        event
        for event in events
        if event.name == "RuntimeExecutionFailed"
    ]
    assert len(failure_events) == 1
    assert failure_events[0].payload["execution_id"] == request.execution_id


def test_execution_evidence_is_idempotent() -> None:
    engine, _, store = _build_engine()
    request = engine.create_request("runtime.observability.idempotent")

    outcome = engine.execute(request, lambda _: "ok")

    assert outcome.success
    first = engine.evidence(request.execution_id)
    second = engine.evidence(request.execution_id)

    assert first is not None
    assert second is not None
    assert first == second
    assert engine.verify_evidence(request.execution_id)
    assert store.records() == (first,)


def test_execution_evidence_integrity_is_verifiable() -> None:
    engine, _, _ = _build_engine()
    request = engine.create_request("runtime.observability.integrity")

    outcome = engine.execute(request, lambda _: {"status": "ok"})

    assert outcome.success

    evidence = engine.evidence(request.execution_id)
    assert evidence is not None
    assert evidence.verify()
    assert engine.verify_evidence(request.execution_id)

    payload = dict(evidence.payload)
    payload["status"] = "tampered"
    assert evidence.payload["result"] == {"status": "ok"}
    assert payload != evidence.payload
    assert evidence.verify()


def test_execution_evidence_preserves_traceability() -> None:
    engine, events, _ = _build_engine()
    request = engine.create_request(
        "runtime.observability.trace",
        correlation_id="corr-runtime-observability",
        trace_id="trace-runtime-observability",
        tenant_id="tenant-runtime-observability",
    )

    outcome = engine.execute(request, lambda _: "ok")

    assert outcome.success

    evidence = engine.evidence(request.execution_id)
    assert evidence is not None
    assert evidence.trace_id == request.trace_id
    assert evidence.payload["correlation_id"] == request.correlation_id
    assert evidence.payload["trace_id"] == request.trace_id
    assert evidence.payload["tenant_id"] == request.tenant_id

    runtime_events = [
        event
        for event in events
        if event.name.startswith("RuntimeExecution")
    ]
    assert runtime_events
    assert all(
        event.metadata.correlation_id == request.correlation_id
        for event in runtime_events
    )
    assert all(
        event.metadata.trace_id == request.trace_id
        for event in runtime_events
    )
    assert all(
        event.metadata.tenant_id == request.tenant_id
        for event in runtime_events
    )
