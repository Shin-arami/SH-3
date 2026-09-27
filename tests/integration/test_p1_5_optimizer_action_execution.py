from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from infrastructure.events.model import Event
from kernel import SH3Kernel
from kernel.meta_controller import MetaController
from kernel.system_optimizer import OptimizationAction, SystemOptimizer


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def publish(self, event: Event) -> Any:
        self.events.append(event)
        return None


def test_optimizer_executes_registered_action_and_rolls_back() -> None:
    optimizer = SystemOptimizer(SH3Kernel())
    state = {"value": 0}

    optimizer.register_action(
        OptimizationAction(
            "raise_value",
            lambda _: state.__setitem__("value", 1),
            lambda _: state.__setitem__("value", 0),
        )
    )

    result = optimizer.execute_action("raise_value")
    assert result.success is True
    assert state["value"] == 1

    rolled_back = optimizer.rollback_action(result)
    assert rolled_back.success is True
    assert rolled_back.rolled_back is True
    assert state["value"] == 0


def test_optimizer_executes_proposed_rebalance_actions() -> None:
    kernel = SH3Kernel()
    for name in ("one", "two", "three", "four", "five", "six", "seven"):
        kernel.context_manager.push(name)
    optimizer = SystemOptimizer(kernel)

    result = optimizer.optimize(execute=True)

    assert result["rebalance"]["actions"] == ["reduce_context_depth"]
    assert result["execution"][0]["action"] == "reduce_context_depth"
    assert result["execution"][0]["success"] is True
    assert kernel.context_manager.snapshot()["depth"] == 6


def test_optimizer_execution_failure_rolls_back_previous_actions() -> None:
    optimizer = SystemOptimizer(SH3Kernel())
    state = {"value": 0}
    optimizer.register_action(
        OptimizationAction(
            "first", lambda _: state.__setitem__("value", 1), lambda _: state.__setitem__("value", 0)
        )
    )

    def fail(_: Mapping[str, Any]) -> None:
        raise RuntimeError("action failure")

    optimizer.register_action(OptimizationAction("second", fail, lambda _: None))
    results = optimizer.execute_actions(("first", "second"), rollback_on_failure=True)

    assert results[0].success is True
    assert results[1].success is False
    assert state["value"] == 0
    assert optimizer.history[-1].rolled_back is True


def test_optimizer_publishes_action_lifecycle_events() -> None:
    publisher = RecordingPublisher()
    optimizer = SystemOptimizer(SH3Kernel(), event_publisher=publisher)
    optimizer.register_action(
        OptimizationAction("custom", lambda _: {"changed": True}, lambda _: None)
    )

    result = optimizer.execute_action("custom")

    assert result.success is True
    assert publisher.events == []


def test_meta_controller_optimize_executes_system_optimizer() -> None:
    kernel = SH3Kernel()
    for name in ("one", "two", "three", "four", "five", "six", "seven"):
        kernel.context_manager.push(name)
    controller = MetaController(kernel)

    result = controller.trigger("optimize", controller.observe())

    assert result["status"] == "optimized"
    assert result["optimization"]["execution"][0]["success"] is True
    assert kernel.context_manager.snapshot()["depth"] == 6
