from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from infrastructure.events.model import Event
from infrastructure.events.propagation import EventPropagationContext
from kernel.core import SH3Kernel
from runtime.context_manager import RuntimeContext
from runtime.core import RuntimeCore
from services.base import Service


@dataclass
class RecordingPublisher:
    events: list[Event]

    def __init__(self) -> None:
        self.events = []

    def publish(self, event: Event) -> Any:
        self.events.append(event)
        return type(
            "PublishResult",
            (),
            {"accepted": True, "queued": True, "delivered": True},
        )()


class RecordingService(Service):
    def _on_start(self) -> None:
        return None


def _context() -> EventPropagationContext:
    return EventPropagationContext.create(
        "integration-correlation",
        trace_id="integration-trace",
        tenant_id="integration-tenant",
    )


def _assert_shared_context(
    events: list[Event],
    context: EventPropagationContext,
) -> None:
    assert events
    assert all(event.metadata.correlation_id == context.correlation_id for event in events)
    assert all(event.metadata.trace_id == context.trace_id for event in events)
    assert all(event.metadata.tenant_id == context.tenant_id for event in events)


def _assert_causation_chain(events: list[Event]) -> None:
    for previous, current in pairwise(events):
        assert current.metadata.causation_id == previous.metadata.event_id


def test_kernel_propagates_shared_context_across_cycle() -> None:
    publisher = RecordingPublisher()
    context = _context()
    kernel = SH3Kernel(event_publisher=publisher)

    result = kernel.execute("integration test", context=context)

    assert result["goal"] == "integration test"
    assert [event.metadata.event_name for event in publisher.events] == [
        "KernelCycleStarted",
        "KernelCycleCompleted",
    ]
    _assert_shared_context(publisher.events, context)
    _assert_causation_chain(publisher.events)


def test_runtime_propagates_runtime_context_trace_and_causation() -> None:
    publisher = RecordingPublisher()
    runtime_context = RuntimeContext("integration-runtime")
    runtime = RuntimeCore(event_publisher=publisher)

    result = runtime.run(
        lambda value: value + 1,
        1,
        context=runtime_context,
    )

    assert result == 2
    events = publisher.events
    assert [event.metadata.event_name for event in events] == [
        "RuntimeExecutionStarted",
        "RuntimeExecutionCompleted",
    ]
    assert all(event.metadata.trace_id == runtime_context.trace_id for event in events)
    assert events[0].metadata.causation_id is None
    assert events[1].metadata.causation_id == events[0].metadata.event_id
    assert events[0].payload["trace_id"] == runtime_context.trace_id
    assert events[1].payload["trace_id"] == runtime_context.trace_id


def test_runtime_pipeline_propagates_trace_and_causation() -> None:
    publisher = RecordingPublisher()
    runtime_context = RuntimeContext("integration-pipeline")
    runtime = RuntimeCore(event_publisher=publisher)

    result = runtime.pipe(
        1,
        lambda value: value + 1,
        lambda value: value * 2,
        context=runtime_context,
    )

    assert result == 4
    events = publisher.events
    assert [event.metadata.event_name for event in events] == [
        "RuntimePipelineStarted",
        "RuntimeExecutionStarted",
        "RuntimeExecutionCompleted",
        "RuntimeExecutionStarted",
        "RuntimeExecutionCompleted",
        "RuntimePipelineCompleted",
    ]
    assert all(event.metadata.trace_id == runtime_context.trace_id for event in events)
    _assert_causation_chain(events)


def test_service_propagates_shared_context_across_lifecycle() -> None:
    publisher = RecordingPublisher()
    context = _context()
    service = RecordingService("integration-service", event_publisher=publisher)

    service.start(context=context)
    service.suspend()
    service.resume()
    service.terminate()

    events = publisher.events
    assert [event.metadata.event_name for event in events] == [
        "ServiceStarted",
        "ServiceSuspended",
        "ServiceResumed",
        "ServiceStopped",
    ]
    _assert_shared_context(events, context)
    _assert_causation_chain(events)


def test_kernel_optimizer_propagates_shared_context() -> None:
    publisher = RecordingPublisher()
    context = _context()
    kernel = SH3Kernel(event_publisher=publisher)

    kernel.optimize(context=context)

    events = publisher.events
    assert [event.metadata.event_name for event in events][:2] == [
        "OptimizationStarted",
        "OptimizationCompleted",
    ]
    _assert_shared_context(events, context)
    _assert_causation_chain(events)


def test_runtime_accepts_external_propagation_context() -> None:
    publisher = RecordingPublisher()
    context = _context()
    runtime_context = RuntimeContext("integration-runtime")

    runtime = RuntimeCore(event_publisher=publisher)
    result = runtime.run(
        lambda value: value + 1,
        1,
        context=runtime_context,
        propagation=context,
    )

    assert result == 2

    events = publisher.events
    assert [event.metadata.event_name for event in events] == [
        "RuntimeExecutionStarted",
        "RuntimeExecutionCompleted",
    ]

    _assert_shared_context(events, context)

    assert events[0].metadata.causation_id == context.causation_id
    assert events[1].metadata.causation_id == events[0].metadata.event_id


def test_runtime_pipeline_accepts_external_propagation_context() -> None:
    publisher = RecordingPublisher()
    context = _context()
    runtime_context = RuntimeContext("integration-pipeline")

    runtime = RuntimeCore(event_publisher=publisher)
    result = runtime.pipe(
        1,
        lambda value: value + 1,
        lambda value: value * 2,
        context=runtime_context,
        propagation=context,
    )

    assert result == 4

    events = publisher.events

    assert [event.metadata.event_name for event in events] == [
        "RuntimePipelineStarted",
        "RuntimeExecutionStarted",
        "RuntimeExecutionCompleted",
        "RuntimeExecutionStarted",
        "RuntimeExecutionCompleted",
        "RuntimePipelineCompleted",
    ]

    _assert_shared_context(events, context)
    _assert_causation_chain(events)
