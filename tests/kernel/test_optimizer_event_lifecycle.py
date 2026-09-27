from __future__ import annotations

from typing import Any

from infrastructure.events.model import Event
from kernel import SH3Kernel
from kernel.meta_controller import MetaController
from kernel.system_optimizer import SystemOptimizer


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def publish(self, event: Event) -> Any:
        self.events.append(event)
        return None


def test_meta_controller_publishes_optimization_events() -> None:
    publisher = RecordingPublisher()
    controller = MetaController(
        SH3Kernel(),
        event_publisher=publisher,
    )

    result = controller.run_cycle()

    assert result["action"] == "heal"
    assert [event.name for event in publisher.events] == [
        "OptimizationDecisionCreated",
        "OptimizationCompleted",
    ]

    assert publisher.events[0].metadata.producer == "optimizer"
    assert publisher.events[1].metadata.producer == "optimizer"


def test_meta_controller_policy_tuning_publishes_events() -> None:
    publisher = RecordingPublisher()
    controller = MetaController(
        SH3Kernel(),
        event_publisher=publisher,
    )

    controller.tune_policy(controller.observe())

    assert [event.name for event in publisher.events] == [
        "PolicyTuningStarted",
        "PolicyTuningCompleted",
    ]

    assert publisher.events[0].payload["tuning_id"]
    assert publisher.events[1].payload["success"] is True


def test_system_optimizer_publishes_lifecycle_events() -> None:
    publisher = RecordingPublisher()
    optimizer = SystemOptimizer(
        SH3Kernel(),
        event_publisher=publisher,
    )

    result = optimizer.optimize()

    assert result["rebalance"]["actions"] == []
    assert [event.name for event in publisher.events] == [
        "OptimizationStarted",
        "OptimizationCompleted",
    ]

    assert publisher.events[0].metadata.producer == "optimizer"
    assert publisher.events[1].metadata.producer == "optimizer"


def test_optimizer_event_publication_failure_does_not_break_operation() -> None:
    class BrokenPublisher:
        def publish(self, event: Event) -> Any:
            raise RuntimeError("publisher failure")

    optimizer = SystemOptimizer(
        SH3Kernel(),
        event_publisher=BrokenPublisher(),
    )

    result = optimizer.optimize()

    assert result["rebalance"]["actions"] == []


def test_meta_controller_without_publisher_preserves_api() -> None:
    controller = MetaController(SH3Kernel())

    result = controller.run_cycle()

    assert result["action"] == "heal"


def test_system_optimizer_without_publisher_preserves_api() -> None:
    optimizer = SystemOptimizer(SH3Kernel())

    result = optimizer.optimize()

    assert result["snapshot"]["context_depth"] == 0
