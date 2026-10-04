from __future__ import annotations

from datetime import UTC, datetime

import pytest

from foundation.Enums.priority import Priority
from runtime.execution import ExecutionRequest, ExecutionSnapshot, ExecutionState
from runtime.state_machine import ExecutionStateMachineError, RuntimeExecutionStateMachine


def _snapshot() -> ExecutionSnapshot:
    request = ExecutionRequest.create(
        "exec-1",
        "runtime.execute",
        priority=Priority.NORMAL,
        correlation_id="corr-1",
        trace_id="trace-1",
    )
    return ExecutionSnapshot.create(
        request,
        now=datetime(2026, 9, 30, 12, 0, tzinfo=UTC),
    )


def test_register_and_get_snapshot() -> None:
    machine = RuntimeExecutionStateMachine()
    snapshot = _snapshot()
    assert machine.register(snapshot) == snapshot
    assert machine.get("exec-1") == snapshot
    assert machine.current_state("exec-1") is ExecutionState.CREATED


def test_register_same_snapshot_is_idempotent() -> None:
    machine = RuntimeExecutionStateMachine()
    snapshot = _snapshot()
    assert machine.register(snapshot) is snapshot
    assert machine.register(snapshot) is snapshot


def test_register_conflicting_snapshot_is_rejected() -> None:
    machine = RuntimeExecutionStateMachine()
    snapshot = _snapshot()
    machine.register(snapshot)
    conflicting = _snapshot()
    conflicting = conflicting.__class__(
        execution_id=conflicting.execution_id,
        operation="different",
        state=conflicting.state,
        priority=conflicting.priority,
        created_at=conflicting.created_at,
        correlation_id=conflicting.correlation_id,
    )
    with pytest.raises(ExecutionStateMachineError):
        machine.register(conflicting)


def test_created_to_queued_to_running() -> None:
    machine = RuntimeExecutionStateMachine()
    machine.register(_snapshot())
    queued_at = datetime(2026, 9, 30, 12, 0, 1, tzinfo=UTC)
    started_at = datetime(2026, 9, 30, 12, 0, 2, tzinfo=UTC)
    queued = machine.transition("exec-1", ExecutionState.QUEUED, now=queued_at)
    running = machine.transition("exec-1", ExecutionState.RUNNING, now=started_at)
    assert queued.state is ExecutionState.QUEUED
    assert queued.queued_at == queued_at
    assert running.state is ExecutionState.RUNNING
    assert running.started_at == started_at
    assert running.attempt == 1


def test_running_to_completed() -> None:
    machine = RuntimeExecutionStateMachine()
    machine.register(_snapshot())

    queued_at = datetime(2026, 9, 30, 12, 0, 1, tzinfo=UTC)
    started_at = datetime(2026, 9, 30, 12, 0, 2, tzinfo=UTC)
    completed_at = datetime(2026, 9, 30, 12, 0, 3, tzinfo=UTC)

    machine.transition("exec-1", ExecutionState.QUEUED, now=queued_at)
    machine.transition("exec-1", ExecutionState.RUNNING, now=started_at)
    completed = machine.transition(
        "exec-1",
        ExecutionState.COMPLETED,
        now=completed_at,
        result={"value": 42},
    )

    assert completed.state is ExecutionState.COMPLETED
    assert completed.completed_at == completed_at
    assert completed.result == {"value": 42}
    assert completed.error_type is None
    assert completed.error_message is None
    assert completed.terminal


@pytest.mark.parametrize(
    "target",
    [
        ExecutionState.COMPLETED,
        ExecutionState.FAILED,
        ExecutionState.CANCEL_REQUESTED,
        ExecutionState.TIMED_OUT,
    ],
)
def test_running_terminal_and_cancel_transitions(target: ExecutionState) -> None:
    machine = RuntimeExecutionStateMachine()
    machine.register(_snapshot())
    machine.transition("exec-1", ExecutionState.QUEUED)
    machine.transition("exec-1", ExecutionState.RUNNING)
    snapshot = machine.transition("exec-1", target)
    assert snapshot.state is target
    if target.terminal:
        assert snapshot.completed_at is not None


def test_cancel_requested_to_cancelled() -> None:
    machine = RuntimeExecutionStateMachine()
    machine.register(_snapshot())
    machine.transition("exec-1", ExecutionState.QUEUED)
    machine.transition("exec-1", ExecutionState.RUNNING)
    requested = machine.transition("exec-1", ExecutionState.CANCEL_REQUESTED)
    cancelled = machine.transition("exec-1", ExecutionState.CANCELLED)
    assert requested.state is ExecutionState.CANCEL_REQUESTED
    assert cancelled.state is ExecutionState.CANCELLED
    assert cancelled.terminal


def test_invalid_transition_is_rejected() -> None:
    machine = RuntimeExecutionStateMachine()
    machine.register(_snapshot())
    with pytest.raises(ExecutionStateMachineError):
        machine.transition("exec-1", ExecutionState.RUNNING)


def test_terminal_state_cannot_transition() -> None:
    machine = RuntimeExecutionStateMachine()
    machine.register(_snapshot())
    machine.transition("exec-1", ExecutionState.QUEUED)
    machine.transition("exec-1", ExecutionState.RUNNING)
    machine.transition("exec-1", ExecutionState.COMPLETED)
    with pytest.raises(ExecutionStateMachineError):
        machine.transition("exec-1", ExecutionState.FAILED)


def test_can_transition() -> None:
    machine = RuntimeExecutionStateMachine()
    machine.register(_snapshot())
    assert machine.can_transition("exec-1", ExecutionState.QUEUED)
    assert not machine.can_transition("exec-1", ExecutionState.RUNNING)


def test_unknown_execution_is_rejected() -> None:
    machine = RuntimeExecutionStateMachine()
    with pytest.raises(ExecutionStateMachineError):
        machine.transition("missing", ExecutionState.QUEUED)


def test_snapshots_are_returned_as_tuple() -> None:
    machine = RuntimeExecutionStateMachine()
    machine.register(_snapshot())
    snapshots = machine.snapshots()
    assert isinstance(snapshots, tuple)
    assert len(snapshots) == 1


def test_remove() -> None:
    machine = RuntimeExecutionStateMachine()
    snapshot = _snapshot()
    machine.register(snapshot)
    assert machine.remove("exec-1") == snapshot
    assert machine.get("exec-1") is None
