from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from runtime.execution import ExecutionRequest, ExecutionState
from runtime.execution_cleanup import RuntimeExecutionCleanupManager
from runtime.execution_controller import RuntimeExecutionController
from runtime.execution_engine import RuntimeExecutionEngine


def request(execution_id: str = "exec-1", timeout: float | None = None) -> ExecutionRequest:
    return ExecutionRequest.create(
        execution_id=execution_id,
        operation="test",
        timeout=timeout,
    )


def test_cleanup_runs_once() -> None:
    manager = RuntimeExecutionCleanupManager()
    calls: list[str] = []
    manager.register("exec-1", lambda: calls.append("cleanup"))
    first = manager.cleanup("exec-1")
    second = manager.cleanup("exec-1")
    assert calls == ["cleanup"]
    assert first.attempted
    assert first.completed
    assert second.attempted is False
    assert second.completed


def test_cleanup_runs_in_registration_order() -> None:
    manager = RuntimeExecutionCleanupManager()
    calls: list[str] = []
    manager.register("exec-1", lambda: calls.append("a"), name="a")
    manager.register("exec-1", lambda: calls.append("b"), name="b")
    manager.register("exec-1", lambda: calls.append("c"), name="c")
    result = manager.cleanup("exec-1")
    assert calls == ["a", "b", "c"]
    assert result.completed
    assert result.failures == ()


def test_cleanup_continues_after_failure() -> None:
    manager = RuntimeExecutionCleanupManager()
    calls: list[str] = []

    def fail() -> None:
        calls.append("fail")
        raise RuntimeError("cleanup failed")

    manager.register("exec-1", fail, name="failed")
    manager.register("exec-1", lambda: calls.append("after"), name="after")
    result = manager.cleanup("exec-1")
    assert calls == ["fail", "after"]
    assert result.failed
    assert len(result.failures) == 1
    assert result.failures[0].name == "failed"
    assert result.failures[0].error_type == "RuntimeError"
    assert result.failures[0].error_message == "cleanup failed"


def test_completed_execution_runs_cleanup() -> None:
    engine = RuntimeExecutionEngine()
    calls: list[str] = []
    execution = request()
    engine.register_cleanup(execution.execution_id, lambda: calls.append("cleanup"))
    outcome = engine.execute(execution, lambda _: "ok")
    assert outcome.success
    assert outcome.state is ExecutionState.COMPLETED
    assert calls == ["cleanup"]
    assert outcome.cleanup is not None
    assert outcome.cleanup.completed


def test_failed_execution_runs_cleanup() -> None:
    engine = RuntimeExecutionEngine()
    calls: list[str] = []
    execution = request()

    def operation(_: object) -> None:
        raise ValueError("boom")

    engine.register_cleanup(execution.execution_id, lambda: calls.append("cleanup"))
    outcome = engine.execute(execution, operation)
    assert outcome.failed
    assert outcome.state is ExecutionState.FAILED
    assert calls == ["cleanup"]
    assert outcome.cleanup is not None
    assert outcome.cleanup.completed


def test_cleanup_failure_does_not_change_execution_result() -> None:
    engine = RuntimeExecutionEngine()
    execution = request()

    def cleanup() -> None:
        raise RuntimeError("resource release failed")

    engine.register_cleanup(execution.execution_id, cleanup, name="resource")
    outcome = engine.execute(execution, lambda _: "ok")
    assert outcome.success
    assert outcome.state is ExecutionState.COMPLETED
    assert outcome.cleanup is not None
    assert outcome.cleanup.failed
    assert outcome.cleanup.failures[0].name == "resource"


def test_controller_cancels_queued_execution_and_cleans_up() -> None:
    manager = RuntimeExecutionCleanupManager()
    engine = RuntimeExecutionEngine(cleanup_manager=manager)
    execution = request("exec-cancel")
    engine.state_machine.register(
        __import__("runtime.execution", fromlist=["ExecutionSnapshot"]).ExecutionSnapshot.create(
            execution,
            now=datetime.now(UTC),
        )
    )
    engine.state_machine.transition("exec-cancel", ExecutionState.QUEUED)
    controller = RuntimeExecutionController(engine.state_machine, manager)
    calls: list[str] = []
    controller.register_cleanup("exec-cancel", lambda: calls.append("cleanup"))
    result = controller.cancel("exec-cancel")
    assert result.state is ExecutionState.CANCELLED
    assert result.cleanup is not None
    assert calls == ["cleanup"]


def test_controller_running_cancel_does_not_cleanup_until_cancelled() -> None:
    manager = RuntimeExecutionCleanupManager()
    engine = RuntimeExecutionEngine(cleanup_manager=manager)
    execution = request("exec-running")
    engine.state_machine.register(
        __import__("runtime.execution", fromlist=["ExecutionSnapshot"]).ExecutionSnapshot.create(
            execution,
            now=datetime.now(UTC),
        )
    )
    engine.state_machine.transition("exec-running", ExecutionState.QUEUED)
    engine.state_machine.transition("exec-running", ExecutionState.RUNNING)
    controller = RuntimeExecutionController(engine.state_machine, manager)
    calls: list[str] = []
    controller.register_cleanup("exec-running", lambda: calls.append("cleanup"))
    requested = controller.cancel("exec-running")
    assert requested.state is ExecutionState.CANCEL_REQUESTED
    assert requested.cleanup is None
    assert calls == []
    completed = controller.complete_cancellation("exec-running")
    assert completed.state is ExecutionState.CANCELLED
    assert completed.cleanup is not None
    assert calls == ["cleanup"]


def test_controller_timeout_cleans_up_at_deadline() -> None:
    manager = RuntimeExecutionCleanupManager()
    engine = RuntimeExecutionEngine(cleanup_manager=manager)
    execution = request("exec-timeout", timeout=5.0)
    started = datetime.now(UTC)
    from runtime.execution import ExecutionSnapshot

    engine.state_machine.register(ExecutionSnapshot.create(execution, now=started))
    engine.state_machine.transition("exec-timeout", ExecutionState.QUEUED, now=started)
    engine.state_machine.transition("exec-timeout", ExecutionState.RUNNING, now=started)
    controller = RuntimeExecutionController(engine.state_machine, manager)
    calls: list[str] = []
    controller.register_cleanup("exec-timeout", lambda: calls.append("cleanup"))
    result = controller.timeout(
        "exec-timeout",
        now=started + timedelta(seconds=5),
    )
    assert result.timed_out
    assert result.state is ExecutionState.TIMED_OUT
    assert result.cleanup is not None
    assert calls == ["cleanup"]


def test_cleanup_rejects_registration_after_terminal_cleanup() -> None:
    manager = RuntimeExecutionCleanupManager()
    manager.cleanup("exec-1")
    with pytest.raises(RuntimeError, match="cleanup already completed"):
        manager.register("exec-1", lambda: None)
