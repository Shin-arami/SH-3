from __future__ import annotations

from datetime import UTC, datetime

import pytest

from foundation.Enums.priority import Priority
from runtime.execution import ExecutionRequest, ExecutionSnapshot, ExecutionState
from runtime.execution_controller import RuntimeExecutionController
from runtime.state_machine import RuntimeExecutionStateMachine


def _snapshot(
    *,
    state: ExecutionState = ExecutionState.CREATED,
    timeout: float | None = 5.0,
    started_at: datetime | None = None,
) -> ExecutionSnapshot:
    created_at = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)
    request = ExecutionRequest.create(
        execution_id="exec-1",
        operation="runtime.execute",
        priority=Priority.NORMAL,
        timeout=timeout,
        correlation_id="corr-1",
    )
    return ExecutionSnapshot(
        execution_id=request.execution_id,
        operation=request.operation,
        state=state,
        priority=request.priority,
        timeout=request.timeout,
        created_at=created_at,
        queued_at=created_at if state is not ExecutionState.CREATED else None,
        started_at=started_at,
        completed_at=None,
        attempt=0,
        result=None,
        error_type=None,
        error_message=None,
        correlation_id=request.correlation_id or request.execution_id,
        causation_id=request.causation_id,
        trace_id=request.trace_id,
        tenant_id=request.tenant_id,
        metadata=request.metadata,
    )


def _controller(snapshot: ExecutionSnapshot) -> RuntimeExecutionController:
    machine = RuntimeExecutionStateMachine()
    machine.register(snapshot)
    return RuntimeExecutionController(machine)


def test_created_can_be_cancelled() -> None:
    controller = _controller(_snapshot())

    result = controller.cancel(
        "exec-1",
        now=datetime(2026, 9, 30, 12, 0, 1, tzinfo=UTC),
    )

    assert result.requested
    assert result.state is ExecutionState.CANCELLED


def test_queued_can_be_cancelled() -> None:
    snapshot = _snapshot(state=ExecutionState.QUEUED)
    controller = _controller(snapshot)

    result = controller.cancel(
        "exec-1",
        now=datetime(2026, 9, 30, 12, 0, 1, tzinfo=UTC),
    )

    assert result.requested
    assert result.state is ExecutionState.CANCELLED


def test_running_requests_cooperative_cancellation() -> None:
    started_at = datetime(2026, 9, 30, 12, 0, 1, tzinfo=UTC)
    controller = _controller(
        _snapshot(state=ExecutionState.RUNNING, started_at=started_at)
    )

    result = controller.cancel(
        "exec-1",
        now=datetime(2026, 9, 30, 12, 0, 2, tzinfo=UTC),
    )

    assert result.requested
    assert result.state is ExecutionState.CANCEL_REQUESTED


def test_cancel_request_is_idempotent() -> None:
    started_at = datetime(2026, 9, 30, 12, 0, 1, tzinfo=UTC)
    controller = _controller(
        _snapshot(state=ExecutionState.RUNNING, started_at=started_at)
    )

    now = datetime(2026, 9, 30, 12, 0, 2, tzinfo=UTC)
    first = controller.cancel("exec-1", now=now)
    second = controller.cancel("exec-1", now=now)

    assert first.state is ExecutionState.CANCEL_REQUESTED
    assert second.state is ExecutionState.CANCEL_REQUESTED
    assert second.requested


def test_cancelled_is_idempotent() -> None:
    controller = _controller(_snapshot(state=ExecutionState.CANCELLED))

    result = controller.cancel(
        "exec-1",
        now=datetime(2026, 9, 30, 12, 0, 1, tzinfo=UTC),
    )

    assert result.requested
    assert result.state is ExecutionState.CANCELLED


@pytest.mark.parametrize(
    "state",
    [
        ExecutionState.COMPLETED,
        ExecutionState.FAILED,
        ExecutionState.TIMED_OUT,
    ],
)
def test_terminal_execution_cannot_be_cancelled(
    state: ExecutionState,
) -> None:
    controller = _controller(_snapshot(state=state))

    result = controller.cancel(
        "exec-1",
        now=datetime(2026, 9, 30, 12, 0, 1, tzinfo=UTC),
    )

    assert not result.requested
    assert result.state is state


def test_running_execution_does_not_timeout_before_deadline() -> None:
    started_at = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)
    controller = _controller(
        _snapshot(state=ExecutionState.RUNNING, started_at=started_at)
    )

    result = controller.timeout(
        "exec-1",
        now=datetime(2026, 9, 30, 12, 0, 4, tzinfo=UTC),
    )

    assert not result.timed_out
    assert result.state is ExecutionState.RUNNING


def test_running_execution_times_out_at_deadline() -> None:
    started_at = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)
    controller = _controller(
        _snapshot(state=ExecutionState.RUNNING, started_at=started_at)
    )

    result = controller.timeout(
        "exec-1",
        now=datetime(2026, 9, 30, 12, 0, 5, tzinfo=UTC),
    )

    assert result.timed_out
    assert result.state is ExecutionState.TIMED_OUT

    snapshot = controller.snapshot("exec-1")
    assert snapshot is not None
    assert snapshot.error_type == "TimeoutError"
    assert snapshot.error_message == "execution timed out"


def test_timeout_after_deadline_is_terminal() -> None:
    started_at = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)
    controller = _controller(
        _snapshot(state=ExecutionState.RUNNING, started_at=started_at)
    )

    now = datetime(2026, 9, 30, 12, 0, 5, tzinfo=UTC)
    first = controller.timeout("exec-1", now=now)
    second = controller.timeout(
        "exec-1",
        now=datetime(2026, 9, 30, 12, 0, 6, tzinfo=UTC),
    )

    assert first.timed_out
    assert second.timed_out
    assert second.state is ExecutionState.TIMED_OUT


def test_execution_without_timeout_is_not_timed_out() -> None:
    started_at = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)
    controller = _controller(
        _snapshot(state=ExecutionState.RUNNING, timeout=None, started_at=started_at)
    )

    result = controller.timeout(
        "exec-1",
        now=datetime(2026, 9, 30, 12, 1, 0, tzinfo=UTC),
    )

    assert not result.timed_out
    assert result.state is ExecutionState.RUNNING


def test_timeout_before_execution_started_does_not_timeout() -> None:
    controller = _controller(_snapshot(state=ExecutionState.QUEUED))

    result = controller.timeout(
        "exec-1",
        now=datetime(2026, 9, 30, 12, 1, 0, tzinfo=UTC),
    )

    assert not result.timed_out
    assert result.state is ExecutionState.QUEUED


def test_missing_execution_is_rejected() -> None:
    controller = _controller(_snapshot())

    with pytest.raises(KeyError, match="execution not found"):
        controller.cancel("missing")


def test_empty_execution_id_is_rejected() -> None:
    controller = _controller(_snapshot())

    with pytest.raises(ValueError, match="execution_id must not be empty"):
        controller.cancel("")

    with pytest.raises(ValueError, match="execution_id must not be empty"):
        controller.timeout("")
