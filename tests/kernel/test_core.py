from __future__ import annotations

import pytest

from cognition.policy import PolicyRule
from foundation.utils.exceptions import SH3Exception
from kernel import SH3Kernel
from kernel.core import SH3Kernel as CoreSH3Kernel


def test_package_exports_kernel() -> None:
    assert SH3Kernel is CoreSH3Kernel


def test_kernel_initialization_wires_default_components() -> None:
    kernel = SH3Kernel()

    assert kernel.kernel_id
    assert kernel.policy.rules == []
    assert kernel.history() == []


def test_execute_returns_and_stores_execution_result() -> None:
    kernel = SH3Kernel()
    kernel.add_policy(PolicyRule("always", score_fn=lambda _: 1.0))

    result = kernel.execute("prepare release notes")

    assert result["kernel_id"] == kernel.kernel_id
    assert result["goal"] == "prepare release notes"
    assert result["plan"]["goal"] == "prepare release notes"
    assert result["decision"] == "always"
    assert result["memory_key"]
    assert kernel.recall(result["memory_key"])["goal"] == "prepare release notes"
    assert kernel.context_manager.snapshot()["depth"] == 0


def test_step_returns_cognitive_state_and_cleans_up_context() -> None:
    kernel = SH3Kernel()

    result = kernel.step("inspect system state")

    assert result["goal"] == "inspect system state"
    assert result["cognitive_state"]["goal"] == "inspect system state"
    assert result["plan"]["goal"] == "inspect system state"
    assert kernel.context_manager.snapshot()["depth"] == 0


@pytest.mark.parametrize("method", ["execute", "step"])
@pytest.mark.parametrize("goal", [None, "", "   "])
def test_goal_methods_validate_goal(method: str, goal: object) -> None:
    kernel = SH3Kernel()

    with pytest.raises((TypeError, ValueError)):
        getattr(kernel, method)(goal)


def test_execute_wraps_unexpected_errors_and_cleans_up_context() -> None:
    kernel = SH3Kernel()

    def fail(_: str) -> object:
        raise ValueError("failure")

    kernel.cognition.run = fail  # type: ignore[method-assign, assignment]

    with pytest.raises(SH3Exception, match="failure") as caught:
        kernel.execute("goal")

    assert isinstance(caught.value.__cause__, ValueError)
    assert kernel.context_manager.snapshot()["depth"] == 0


def test_history_validates_limit_and_snapshot_reports_state() -> None:
    kernel = SH3Kernel()
    kernel.add_policy(PolicyRule("always"))

    with pytest.raises(TypeError):
        kernel.history("1")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        kernel.history(-1)

    snapshot = kernel.snapshot()
    assert snapshot["kernel_id"] == kernel.kernel_id
    assert snapshot["context"]["depth"] == 0
    assert snapshot["memory"] == []
    assert snapshot["policy_rules"] == 1


def test_kernel_initialization_wires_management_components() -> None:
    kernel = SH3Kernel()

    assert kernel.learning_loop.kernel is kernel
    assert kernel.meta_controller.kernel is kernel
    assert kernel.system_optimizer.kernel is kernel
    assert kernel.meta_controller.healer is not None


def test_learning_cycle_uses_kernel_learning_loop() -> None:
    kernel = SH3Kernel()
    kernel.add_policy(PolicyRule("always", score_fn=lambda _: 1.0))

    execution = kernel.execute("prepare release notes")
    result = kernel.learning_cycle(execution)

    assert result["loop_id"] == kernel.learning_loop.loop_id
    assert result["experience"]["goal"] == "prepare release notes"
    assert result["memory_key"]
    assert result["score"] >= 0.0
    assert result["score"] <= 1.0


def test_meta_cycle_uses_kernel_meta_controller() -> None:
    kernel = SH3Kernel()

    result = kernel.meta_cycle()

    assert result["meta_id"] == kernel.meta_controller.meta_id
    assert "snapshot" in result
    assert "health" in result
    assert "action" in result
    assert "result" in result


def test_optimize_uses_kernel_system_optimizer() -> None:
    kernel = SH3Kernel()

    result = kernel.optimize()

    assert result["optimizer_id"] == kernel.system_optimizer.optimizer_id
    assert "snapshot" in result
    assert "bottlenecks" in result
    assert "module_scores" in result
    assert "rebalance" in result
    assert "prune" in result


def test_kernel_execute_safe_uses_self_healing() -> None:
    kernel = SH3Kernel()

    result = kernel.execute_safe(lambda: (_ for _ in ()).throw(ValueError("failure")))

    assert result["status"] == "context_rebuilt"
    assert result["trace_id"]


def test_kernel_snapshot_contains_management_state() -> None:
    kernel = SH3Kernel()

    snapshot = kernel.snapshot()

    assert snapshot["kernel_id"] == kernel.kernel_id
    assert snapshot["context"]["depth"] == 0
    assert snapshot["memory"] == []
    assert snapshot["policy_rules"] == 0
    assert snapshot["learning_loop_id"] == kernel.learning_loop.loop_id
    assert snapshot["meta_controller_id"] == kernel.meta_controller.meta_id
    assert snapshot["system_optimizer_id"] == kernel.system_optimizer.optimizer_id
