from __future__ import annotations

from typing import Any

import pytest

from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.utils.exceptions import RuntimeException
from infrastructure.event_bus import EventBus, EventBusPublisher, EventSubscription
from infrastructure.events.model import Event
from runtime.core import RuntimeContext, RuntimeCore


def _publisher_and_events() -> tuple[EventBus, EventBusPublisher, list[Event]]:
    bus = EventBus()
    events: list[Event] = []
    bus.subscribe(
        EventSubscription(
            subscriber_id="test-runtime-propagation",
            handler=lambda event: events.append(event),
        )
    )
    return bus, EventBusPublisher(bus), events


def _events_by_name(events: list[Event], name: str) -> list[Event]:
    return [event for event in events if event.metadata.event_name == name]


def test_run_propagates_correlation_and_causation() -> None:
    bus, publisher, events = _publisher_and_events()
    runtime = RuntimeCore(event_publisher=publisher)

    assert runtime.run(lambda: "result") == "result"

    started = _events_by_name(events, "RuntimeExecutionStarted")[0]
    completed = _events_by_name(events, "RuntimeExecutionCompleted")[0]

    assert started.metadata.correlation_id == started.payload["execution_id"]
    assert started.metadata.causation_id is None
    assert completed.metadata.correlation_id == started.metadata.correlation_id
    assert completed.metadata.causation_id == started.metadata.event_id
    assert completed.payload["execution_id"] == started.payload["execution_id"]
    bus.close()


def test_run_propagates_trace_id() -> None:
    bus, publisher, events = _publisher_and_events()
    runtime = RuntimeCore(event_publisher=publisher)
    context = RuntimeContext("trace-test")
    context.trace_id = "trace-runtime-1"

    assert runtime.run(lambda: 42, context=context) == 42

    runtime_events = [
        event
        for event in events
        if event.metadata.event_name
        in {"RuntimeExecutionStarted", "RuntimeExecutionCompleted"}
    ]

    assert len(runtime_events) == 2
    assert all(event.metadata.trace_id == "trace-runtime-1" for event in runtime_events)
    assert all(event.payload["trace_id"] == "trace-runtime-1" for event in runtime_events)
    bus.close()


def test_pipe_propagates_correlation_and_causation_chain() -> None:
    bus, publisher, events = _publisher_and_events()
    runtime = RuntimeCore(event_publisher=publisher)

    assert runtime.pipe(1, lambda value: value + 1, lambda value: value * 2) == 4

    pipeline_started = _events_by_name(events, "RuntimePipelineStarted")[0]
    executions_started = _events_by_name(events, "RuntimeExecutionStarted")
    executions_completed = _events_by_name(events, "RuntimeExecutionCompleted")
    pipeline_completed = _events_by_name(events, "RuntimePipelineCompleted")

    assert len(executions_started) == 2
    assert len(executions_completed) == 2
    assert len(pipeline_completed) == 1

    pipeline_id = pipeline_started.payload["pipeline_id"]
    assert pipeline_started.metadata.correlation_id == pipeline_id
    assert pipeline_started.metadata.causation_id is None

    assert executions_started[0].metadata.correlation_id == pipeline_id
    assert executions_started[0].metadata.causation_id == pipeline_started.metadata.event_id
    assert executions_completed[0].metadata.correlation_id == pipeline_id
    assert executions_completed[0].metadata.causation_id == executions_started[0].metadata.event_id

    assert executions_started[1].metadata.correlation_id == pipeline_id
    assert executions_started[1].metadata.causation_id == executions_completed[0].metadata.event_id
    assert executions_completed[1].metadata.correlation_id == pipeline_id
    assert executions_completed[1].metadata.causation_id == executions_started[1].metadata.event_id

    assert pipeline_completed[0].metadata.correlation_id == pipeline_id
    assert pipeline_completed[0].metadata.causation_id == executions_completed[1].metadata.event_id
    bus.close()


def test_pipe_propagates_trace_id_to_all_events() -> None:
    bus, publisher, events = _publisher_and_events()
    runtime = RuntimeCore(event_publisher=publisher)
    context = RuntimeContext("pipeline-trace")
    context.trace_id = "trace-pipeline-1"

    assert runtime.pipe(2, lambda value: value + 3, lambda value: value * 4, context=context) == 20

    pipeline_events = [
        event
        for event in events
        if event.metadata.event_name.startswith("RuntimePipeline")
        or event.metadata.event_name.startswith("RuntimeExecution")
    ]

    assert len(pipeline_events) == 6
    assert all(event.metadata.trace_id == "trace-pipeline-1" for event in pipeline_events)
    assert all(event.payload["trace_id"] == "trace-pipeline-1" for event in pipeline_events)
    bus.close()


def test_pipe_failure_preserves_propagation_chain() -> None:
    bus, publisher, events = _publisher_and_events()
    runtime = RuntimeCore(event_publisher=publisher)

    def fail(_: Any) -> Any:
        raise ValueError("pipeline failure")

    with pytest.raises(RuntimeException):
        runtime.pipe(1, lambda value: value + 1, fail)

    pipeline_started = _events_by_name(events, "RuntimePipelineStarted")[0]
    executions_started = _events_by_name(events, "RuntimeExecutionStarted")
    executions_completed = _events_by_name(events, "RuntimeExecutionCompleted")
    executions_failed = _events_by_name(events, "RuntimeExecutionFailed")
    pipeline_failed = _events_by_name(events, "RuntimePipelineFailed")[0]

    assert len(executions_started) == 2
    assert len(executions_completed) == 1
    assert len(executions_failed) == 1

    correlation_id = pipeline_started.metadata.correlation_id
    assert executions_started[0].metadata.correlation_id == correlation_id
    assert executions_completed[0].metadata.correlation_id == correlation_id
    assert executions_started[1].metadata.correlation_id == correlation_id
    assert executions_failed[0].metadata.correlation_id == correlation_id
    assert pipeline_failed.metadata.correlation_id == correlation_id

    assert executions_started[0].metadata.causation_id == pipeline_started.metadata.event_id
    assert executions_completed[0].metadata.causation_id == executions_started[0].metadata.event_id
    assert executions_started[1].metadata.causation_id == executions_completed[0].metadata.event_id
    assert executions_failed[0].metadata.causation_id == executions_started[1].metadata.event_id
    assert pipeline_failed.metadata.causation_id == executions_failed[0].metadata.event_id
    bus.close()


def test_runtime_event_publisher_failure_does_not_break_execution() -> None:
    class FailingPublisher:
        def publish(self, event: Event) -> Any:
            raise RuntimeError(f"publish failed: {event.metadata.event_name}")

    runtime = RuntimeCore(event_publisher=FailingPublisher())

    assert runtime.run(lambda: "ok") == "ok"
    assert runtime.pipe(1, lambda value: value + 1) == 2


def test_runtime_without_publisher_preserves_existing_behavior() -> None:
    runtime = RuntimeCore()

    assert runtime.run(lambda: "ok") == "ok"
    assert runtime.pipe(2, lambda value: value * 3, lambda value: value + 1) == 7


def test_runtime_events_use_expected_categories_and_types() -> None:
    bus, publisher, events = _publisher_and_events()
    runtime = RuntimeCore(event_publisher=publisher)

    assert runtime.run(lambda: "ok") == "ok"
    assert runtime.pipe(1, lambda value: value + 1) == 2

    expected = {
        "RuntimeExecutionStarted": (Category.EXECUTION, EventType.START),
        "RuntimeExecutionCompleted": (Category.EXECUTION, EventType.COMPLETE),
        "RuntimePipelineStarted": (Category.PIPELINE, EventType.START),
        "RuntimePipelineCompleted": (Category.PIPELINE, EventType.COMPLETE),
    }

    for name, (category, event_type) in expected.items():
        matching = _events_by_name(events, name)
        assert matching
        assert all(event.category is category for event in matching)
        assert all(event.event_type is event_type for event in matching)
    bus.close()
