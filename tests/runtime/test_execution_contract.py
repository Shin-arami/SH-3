from __future__ import annotations

from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, cast

import pytest

from foundation.Enums.priority import Priority
from foundation.version import EVENT_SCHEMA_VERSION
from runtime.execution import ExecutionRequest, ExecutionSnapshot, ExecutionState


def test_terminal_states() -> None:
    terminal = {
        ExecutionState.COMPLETED,
        ExecutionState.FAILED,
        ExecutionState.CANCELLED,
        ExecutionState.TIMED_OUT,
    }
    assert all(state.terminal for state in terminal)
    assert all(not state.terminal for state in ExecutionState if state not in terminal)


def test_execution_request_create_defaults_correlation_id() -> None:
    request = ExecutionRequest.create("exec-1", "runtime.execute")
    assert request.execution_id == "exec-1"
    assert request.operation == "runtime.execute"
    assert request.priority is Priority.NORMAL
    assert request.correlation_id == "exec-1"
    assert request.timeout is None


def test_execution_request_payload_and_metadata_are_immutable() -> None:
    payload = {"value": 1}
    metadata = {"source": "test"}
    request = ExecutionRequest.create("exec-1", "runtime.execute", payload=payload, metadata=metadata)
    assert isinstance(request.payload, MappingProxyType)
    assert isinstance(request.metadata, MappingProxyType)
    with pytest.raises(TypeError):
        cast(dict[str, Any], request.payload)["value"] = 2
    with pytest.raises(TypeError):
        cast(dict[str, Any], request.metadata)["source"] = "changed"


def test_execution_request_rejects_invalid_timeout() -> None:
    with pytest.raises(ValueError):
        ExecutionRequest.create("exec-1", "runtime.execute", timeout=0)
    with pytest.raises(ValueError):
        ExecutionRequest.create("exec-1", "runtime.execute", timeout=-1)


def test_execution_request_rejects_empty_identity() -> None:
    with pytest.raises(ValueError):
        ExecutionRequest.create("", "runtime.execute")
    with pytest.raises(ValueError):
        ExecutionRequest.create("exec-1", "")


def test_execution_snapshot_create() -> None:
    timestamp = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    request = ExecutionRequest.create(
        "exec-1",
        "runtime.execute",
        priority=Priority.HIGH,
        timeout=10.0,
        trace_id="trace-1",
        metadata={"source": "test"},
    )
    snapshot = ExecutionSnapshot.create(request, now=timestamp)
    assert snapshot.execution_id == "exec-1"
    assert snapshot.operation == "runtime.execute"
    assert snapshot.state is ExecutionState.CREATED
    assert snapshot.priority is Priority.HIGH
    assert snapshot.created_at == timestamp
    assert snapshot.timeout == 10.0
    assert snapshot.correlation_id == "exec-1"
    assert snapshot.trace_id == "trace-1"
    assert snapshot.event_schema_version == EVENT_SCHEMA_VERSION
    assert not snapshot.terminal


def test_execution_snapshot_requires_timezone_aware_timestamps() -> None:
    request = ExecutionRequest.create("exec-1", "runtime.execute")
    with pytest.raises(ValueError):
        ExecutionSnapshot.create(request, now=datetime(2026, 9, 30, 12, 0))


def test_execution_snapshot_rejects_negative_attempt() -> None:
    timestamp = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    with pytest.raises(ValueError):
        ExecutionSnapshot(
            execution_id="exec-1",
            operation="runtime.execute",
            state=ExecutionState.CREATED,
            priority=Priority.NORMAL,
            created_at=timestamp,
            correlation_id="exec-1",
            attempt=-1,
        )


def test_execution_snapshot_metadata_is_immutable() -> None:
    timestamp = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    snapshot = ExecutionSnapshot(
        execution_id="exec-1",
        operation="runtime.execute",
        state=ExecutionState.CREATED,
        priority=Priority.NORMAL,
        created_at=timestamp,
        correlation_id="exec-1",
        metadata={"source": "test"},
    )
    assert isinstance(snapshot.metadata, MappingProxyType)
    with pytest.raises(TypeError):
        cast(dict[str, Any], snapshot.metadata)["source"] = "changed"


def test_request_context_matches_request() -> None:
    request = ExecutionRequest.create(
        execution_id="exec-1",
        operation="test",
        correlation_id="corr-1",
        trace_id="trace-1",
    )

    context = request.context

    assert context.execution_id == request.execution_id
    assert context.correlation_id == request.correlation_id
    assert context.trace_id == request.trace_id
    assert context.attempt == 0


def test_snapshot_context_preserves_attempt_and_propagation() -> None:
    request = ExecutionRequest.create(
        execution_id="exec-1",
        operation="test",
        correlation_id="corr-1",
        causation_id="event-1",
        trace_id="trace-1",
        tenant_id="tenant-1",
    )

    snapshot = ExecutionSnapshot.create(request)
    context = snapshot.context

    assert context.execution_id == snapshot.execution_id
    assert context.correlation_id == snapshot.correlation_id
    assert context.causation_id == snapshot.causation_id
    assert context.trace_id == snapshot.trace_id
    assert context.tenant_id == snapshot.tenant_id
    assert context.attempt == snapshot.attempt
