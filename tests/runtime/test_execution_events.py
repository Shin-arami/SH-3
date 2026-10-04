from __future__ import annotations

from foundation.Enums.event import EventType
from foundation.Enums.priority import Priority
from infrastructure.event_bus import EventBus, EventBusPublisher
from infrastructure.event_bus.router import EventSubscription
from infrastructure.events.model import Event
from runtime.execution import ExecutionRequest
from runtime.execution_engine import RuntimeExecutionEngine


def _build_bus() -> tuple[EventBus, EventBusPublisher, list[Event]]:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []

    bus.subscribe(
        EventSubscription(
            subscriber_id="runtime-test",
            handler=events.append,
        )
    )
    return bus, publisher, events


def _request() -> ExecutionRequest:
    return ExecutionRequest.create(
        execution_id="runtime-event-test",
        operation="runtime.execute",
        priority=Priority.NORMAL,
        correlation_id="corr-runtime",
        trace_id="trace-runtime",
        tenant_id="tenant-runtime",
    )


def test_engine_publishes_execution_lifecycle_events() -> None:
    _, publisher, events = _build_bus()
    engine = RuntimeExecutionEngine(event_publisher=publisher)

    outcome = engine.execute(_request(), lambda _: "ok")

    assert outcome.success

    names = [event.name for event in events]
    assert names == [
        "RuntimeExecutionSubmitted",
        "RuntimeExecutionStarted",
        "RuntimeExecutionCompleted",
    ]

    submitted, started, completed = events

    assert submitted.event_type is EventType.CREATED
    assert started.event_type is EventType.START
    assert completed.event_type is EventType.COMPLETE

    assert submitted.metadata.correlation_id == "corr-runtime"
    assert started.metadata.correlation_id == "corr-runtime"
    assert completed.metadata.correlation_id == "corr-runtime"

    assert submitted.metadata.trace_id == "trace-runtime"
    assert started.metadata.trace_id == "trace-runtime"
    assert completed.metadata.trace_id == "trace-runtime"

    assert submitted.metadata.tenant_id == "tenant-runtime"
    assert started.metadata.tenant_id == "tenant-runtime"
    assert completed.metadata.tenant_id == "tenant-runtime"

    assert started.metadata.causation_id == submitted.id
    assert completed.metadata.causation_id == started.id


def test_engine_publishes_failure_event() -> None:
    _, publisher, events = _build_bus()
    engine = RuntimeExecutionEngine(event_publisher=publisher)

    def fail(_: object) -> None:
        raise ValueError("boom")

    outcome = engine.execute(_request(), fail)

    assert outcome.failed

    names = [event.name for event in events]
    assert names == [
        "RuntimeExecutionSubmitted",
        "RuntimeExecutionStarted",
        "RuntimeExecutionFailed",
    ]

    submitted, started, failed = events

    assert submitted.event_type is EventType.CREATED
    assert started.event_type is EventType.START
    assert failed.event_type is EventType.FAILURE

    assert started.metadata.causation_id == submitted.id
    assert failed.metadata.causation_id == started.id


def test_cleanup_failure_publishes_cleanup_failed() -> None:
    _, publisher, events = _build_bus()
    engine = RuntimeExecutionEngine(event_publisher=publisher)
    execution = _request()

    engine.register_cleanup(
        execution.execution_id,
        lambda: (_ for _ in ()).throw(RuntimeError("cleanup failed")),
        name="resource",
    )

    outcome = engine.execute(execution, lambda _: "ok")

    assert outcome.success
    assert outcome.cleanup is not None
    assert outcome.cleanup.failed

    names = [event.name for event in events]

    assert names == [
        "RuntimeExecutionSubmitted",
        "RuntimeExecutionStarted",
        "RuntimeExecutionCompleted",
        "CleanupFailed",
    ]

    cleanup_failed = events[-1]

    assert cleanup_failed.event_type is EventType.FAILURE
    assert cleanup_failed.metadata.causation_id == events[2].id
    assert cleanup_failed.payload["execution_id"] == execution.execution_id
    assert cleanup_failed.payload["failures"][0]["name"] == "resource"
