from __future__ import annotations

from itertools import pairwise

from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from infrastructure.event_bus import EventBus, EventBusPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from kernel.core import SH3Kernel
from runtime.core import RuntimeCore
from services.base import Service


class RecordingService(Service):
    def _on_start(self) -> None:
        return None

    def _on_terminate(self) -> None:
        return None


def _publisher_and_events() -> tuple[EventBus, EventBusPublisher, list[Event]]:
    bus = EventBus()
    events: list[Event] = []
    bus.subscribe(
        EventSubscription(
            subscriber_id="test-cross-layer-event-contract",
            handler=lambda event: events.append(event),
        )
    )
    return bus, EventBusPublisher(bus), events


def _root_context() -> EventPropagationContext:
    return EventPropagationContext.create(
        "e2e-correlation",
        trace_id="e2e-trace",
        tenant_id="e2e-tenant",
    )


def _handoff(events: list[Event]) -> EventPropagationContext:
    assert events
    return EventPropagationContext.from_event(events[-1])


def _assert_common_context(
    events: list[Event],
    context: EventPropagationContext,
) -> None:
    assert events
    assert all(
        event.metadata.correlation_id == context.correlation_id
        for event in events
    )
    assert all(
        event.metadata.trace_id == context.trace_id
        for event in events
    )
    assert all(
        event.metadata.tenant_id == context.tenant_id
        for event in events
    )


def _assert_causation_chain(events: list[Event]) -> None:
    assert events
    assert events[0].metadata.causation_id is None
    for previous, current in pairwise(events):
        assert current.metadata.causation_id == previous.metadata.event_id


def _assert_unique_event_ids(events: list[Event]) -> None:
    event_ids = [event.metadata.event_id for event in events]
    assert len(event_ids) == len(set(event_ids))


def test_cross_layer_event_contract_e2e() -> None:
    bus, publisher, events = _publisher_and_events()
    kernel = SH3Kernel(event_publisher=publisher)
    context = _root_context()

    try:
        kernel.execute("cross-layer integration", context=context)

        assert [
            event.metadata.event_name
            for event in events
        ] == [
            "KernelCycleStarted",
            "KernelCycleCompleted",
        ]

        kernel_context = _handoff(events)

        runtime = RuntimeCore(
            name="e2e-runtime",
            event_publisher=publisher,
        )
        assert runtime.run(
            lambda: "runtime-result",
            propagation=kernel_context,
        ) == "runtime-result"

        assert [
            event.metadata.event_name
            for event in events
        ] == [
            "KernelCycleStarted",
            "KernelCycleCompleted",
            "RuntimeExecutionStarted",
            "RuntimeExecutionCompleted",
        ]

        runtime_context = _handoff(events)

        service = RecordingService(
            "e2e-service",
            event_publisher=publisher,
        )
        service.start(context=runtime_context)

        assert events[-1].metadata.event_name == "ServiceStarted"

        service_context = _handoff(events)

        kernel.optimize(context=service_context)

        assert [
            event.metadata.event_name
            for event in events
        ] == [
            "KernelCycleStarted",
            "KernelCycleCompleted",
            "RuntimeExecutionStarted",
            "RuntimeExecutionCompleted",
            "ServiceStarted",
            "OptimizationStarted",
            "OptimizationCompleted",
        ]

        optimizer_context = _handoff(events)

        service.terminate(context=optimizer_context)

        assert [
            event.metadata.event_name
            for event in events
        ] == [
            "KernelCycleStarted",
            "KernelCycleCompleted",
            "RuntimeExecutionStarted",
            "RuntimeExecutionCompleted",
            "ServiceStarted",
            "OptimizationStarted",
            "OptimizationCompleted",
            "ServiceStopped",
        ]

        _assert_common_context(events, context)
        _assert_causation_chain(events)
        _assert_unique_event_ids(events)

        assert all(event.metadata.event_version == "1.0.0" for event in events)
        assert events[0].metadata.correlation_id == context.correlation_id
        assert events[0].metadata.trace_id == context.trace_id
        assert events[0].metadata.tenant_id == context.tenant_id

        expected_contract: dict[str, tuple[Category, EventType]] = {
            "KernelCycleStarted": (Category.LIFECYCLE, EventType.START),
            "KernelCycleCompleted": (Category.LIFECYCLE, EventType.COMPLETE),
            "RuntimeExecutionStarted": (Category.EXECUTION, EventType.START),
            "RuntimeExecutionCompleted": (Category.EXECUTION, EventType.COMPLETE),
            "ServiceStarted": (Category.COMPONENT, EventType.START),
            "OptimizationStarted": (Category.ACTION, EventType.START),
            "OptimizationCompleted": (Category.ACTION, EventType.COMPLETE),
            "ServiceStopped": (Category.COMPONENT, EventType.STOP),
        }

        for event in events:
            expected_category, expected_type = expected_contract[
                event.metadata.event_name
            ]
            assert event.category is expected_category
            assert event.event_type is expected_type
    finally:
        bus.close()


def test_cross_layer_event_contract_handoff_preserves_context() -> None:
    bus, publisher, events = _publisher_and_events()
    kernel = SH3Kernel(event_publisher=publisher)
    root = _root_context()

    try:
        kernel.execute("handoff integration", context=root)

        kernel_event = events[-1]
        kernel_context = EventPropagationContext.from_event(kernel_event)

        assert kernel_context.correlation_id == root.correlation_id
        assert kernel_context.causation_id == kernel_event.metadata.event_id
        assert kernel_context.trace_id == root.trace_id
        assert kernel_context.tenant_id == root.tenant_id

        runtime = RuntimeCore(event_publisher=publisher)
        runtime.run(lambda: 42, propagation=kernel_context)

        runtime_event = events[-1]
        runtime_context = EventPropagationContext.from_event(runtime_event)

        assert runtime_context.correlation_id == root.correlation_id
        assert runtime_context.causation_id == runtime_event.metadata.event_id
        assert runtime_context.trace_id == root.trace_id
        assert runtime_context.tenant_id == root.tenant_id

        service = RecordingService(
            "handoff-service",
            event_publisher=publisher,
        )
        service.start(context=runtime_context)

        service_event = events[-1]
        service_context = EventPropagationContext.from_event(service_event)

        assert service_context.correlation_id == root.correlation_id
        assert service_context.causation_id == service_event.metadata.event_id
        assert service_context.trace_id == root.trace_id
        assert service_context.tenant_id == root.tenant_id

        kernel.optimize(context=service_context)

        optimizer_events = events[-2:]
        assert [event.metadata.event_name for event in optimizer_events] == [
            "OptimizationStarted",
            "OptimizationCompleted",
        ]
        assert all(
            event.metadata.correlation_id == root.correlation_id
            for event in optimizer_events
        )
        assert all(
            event.metadata.trace_id == root.trace_id
            for event in optimizer_events
        )
        assert all(
            event.metadata.tenant_id == root.tenant_id
            for event in optimizer_events
        )

        service.terminate(context=_handoff(events))
    finally:
        bus.close()
