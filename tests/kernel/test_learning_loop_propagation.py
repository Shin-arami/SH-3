from __future__ import annotations

from typing import Any

from infrastructure.events import Event, EventPropagationContext
from kernel import SH3Kernel
from kernel.learning_loop import LearningLoop


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def publish(self, event: Event) -> Any:
        self.events.append(event)
        return None


def test_learning_propagates_context() -> None:
    publisher = RecordingPublisher()
    kernel = SH3Kernel()
    loop = LearningLoop(kernel, event_publisher=publisher)
    context = EventPropagationContext.create(
        correlation_id="workflow-learning-001",
        trace_id="trace-learning-001",
        tenant_id="tenant-learning-001",
    )

    kernel.add_policy(
        __import__("cognition.policy", fromlist=["PolicyRule"]).PolicyRule(
            "always",
            score_fn=lambda _: 1.0,
        )
    )

    loop.run(kernel.execute("learning propagation"), context=context)

    assert publisher.events
    assert all(
        event.metadata.correlation_id == "workflow-learning-001"
        for event in publisher.events
    )
    assert all(
        event.metadata.trace_id == "trace-learning-001"
        for event in publisher.events
    )
    assert all(
        event.metadata.tenant_id == "tenant-learning-001"
        for event in publisher.events
    )


def test_learning_events_form_causation_chain() -> None:
    publisher = RecordingPublisher()
    kernel = SH3Kernel()
    loop = LearningLoop(kernel, event_publisher=publisher)

    loop.run({"goal": "", "plan": {"tree": {}}})

    assert publisher.events
    assert publisher.events[0].metadata.causation_id is None

    for previous, current in zip(publisher.events, publisher.events[1:], strict=False):
        assert current.metadata.causation_id == previous.metadata.event_id


def test_learning_accepts_stored_propagation_context() -> None:
    publisher = RecordingPublisher()
    kernel = SH3Kernel()
    loop = LearningLoop(kernel, event_publisher=publisher)

    context = EventPropagationContext.create(
        correlation_id="workflow-learning-002",
        trace_id="trace-learning-002",
    )
    loop.set_propagation_context(context)

    loop.run({"goal": "", "plan": {"tree": {}}})

    assert publisher.events
    assert all(
        event.metadata.correlation_id == "workflow-learning-002"
        for event in publisher.events
    )
    assert all(
        event.metadata.trace_id == "trace-learning-002"
        for event in publisher.events
    )


def test_learning_publisher_failure_does_not_break_execution() -> None:
    class BrokenPublisher:
        def publish(self, event: Event) -> Any:
            raise RuntimeError("publisher failure")

    kernel = SH3Kernel()
    loop = LearningLoop(
        kernel,
        event_publisher=BrokenPublisher(),
    )

    result = loop.run({"goal": "", "plan": {"tree": {}}})

    assert result["score"] == 0.0
